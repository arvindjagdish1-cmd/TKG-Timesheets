import logging

from allauth.account.utils import perform_login
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.contrib.auth import get_user_model
from django.shortcuts import redirect

logger = logging.getLogger(__name__)


class DomainRestrictedSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Enforces:
      - allowed email domains (ALLOWED_EMAIL_DOMAINS)
      - optional allowed tenant IDs (ALLOWED_TENANT_IDS)

    This runs after Microsoft authenticates the user, but before the user is logged in.
    """

    def pre_social_login(self, request, sociallogin):
        email = self._extract_email(sociallogin)
        if not email:
            logger.warning("Microsoft login blocked: no email returned.")
            raise PermissionDenied("No email address returned by Microsoft.")

        email = email.strip().lower()

        # 1) Domain allowlist
        allowed_domains = getattr(settings, "ALLOWED_EMAIL_DOMAINS", []) or []
        if allowed_domains:
            domain = email.split("@")[-1].lower()
            allowed = {d.strip().lower() for d in allowed_domains if d.strip()}
            if domain not in allowed:
                logger.warning("Microsoft login blocked: domain %s not allowed.", domain)
                raise PermissionDenied("This account is not allowed to access this application.")

        # 2) Tenant allowlist (optional hardening)
        allowed_tenants = getattr(settings, "ALLOWED_TENANT_IDS", []) or []
        if allowed_tenants:
            tid = self._extract_tenant_id(sociallogin)
            allowed = {t.strip() for t in allowed_tenants if t.strip()}
            if not tid or tid not in allowed:
                logger.warning("Microsoft login blocked: tenant %s not allowed.", tid)
                raise PermissionDenied("This tenant is not allowed to access this application.")

        # 3) Roster allowlist (must exist in Users table)
        User = get_user_model()
        existing_user = User.objects.filter(email=email, is_active=True).first()
        if not existing_user:
            logger.warning("Microsoft login blocked: %s not on roster.", email)
            raise PermissionDenied("This account is not on the approved roster.")

        # Normalize stored email
        sociallogin.user.email = email

        # Keep basic profile data up to date when possible
        self._sync_profile_details(existing_user, sociallogin)

        # 4) If the user already exists, auto-connect and login
        if not sociallogin.is_existing:
            sociallogin.connect(request, existing_user)
            perform_login(request, existing_user, email_verification="none")
            raise ImmediateHttpResponse(redirect(settings.LOGIN_REDIRECT_URL))

    def on_authentication_error(
        self,
        request,
        provider_id,
        error=None,
        exception=None,
        extra_context=None,
    ):
        logger.warning(
            "Microsoft authentication error: provider=%s error=%s exception=%s context=%s",
            provider_id,
            error,
            exception,
            extra_context,
        )
        return super().on_authentication_error(
            request,
            provider_id,
            error=error,
            exception=exception,
            extra_context=extra_context,
        )

    @staticmethod
    def _extract_email(sociallogin):
        extra = getattr(sociallogin.account, "extra_data", {}) or {}

        # Microsoft commonly returns:
        # - mail
        # - userPrincipalName
        # - email (sometimes)
        for key in ("email", "mail", "userPrincipalName", "preferred_username"):
            val = extra.get(key)
            if val:
                return val

        # fallback: allauth sometimes sets sociallogin.user.email
        user_email = getattr(sociallogin.user, "email", None)
        return user_email

    @staticmethod
    def _extract_tenant_id(sociallogin):
        extra = getattr(sociallogin.account, "extra_data", {}) or {}

        # In Microsoft ID tokens, tenant id is typically "tid"
        for key in ("tid", "tenantId", "tenant_id"):
            val = extra.get(key)
            if val:
                return str(val).strip()

        return None

    @staticmethod
    def _extract_name_parts(sociallogin):
        extra = getattr(sociallogin.account, "extra_data", {}) or {}
        first_name = extra.get("given_name") or extra.get("givenName") or ""
        last_name = extra.get("family_name") or extra.get("familyName") or ""

        if not first_name and not last_name:
            display_name = extra.get("name") or extra.get("displayName") or ""
            if display_name:
                parts = display_name.strip().split()
                if parts:
                    first_name = parts[0]
                    if len(parts) > 1:
                        last_name = " ".join(parts[1:])

        return first_name.strip(), last_name.strip()

    @staticmethod
    def _extract_job_title(sociallogin):
        extra = getattr(sociallogin.account, "extra_data", {}) or {}
        title = extra.get("jobTitle") or extra.get("job_title") or ""
        return str(title).strip()

    def _sync_profile_details(self, user, sociallogin):
        first_name, last_name = self._extract_name_parts(sociallogin)
        updated = False

        if first_name and not user.first_name:
            user.first_name = first_name
            updated = True
        if last_name and not user.last_name:
            user.last_name = last_name
            updated = True

        if updated:
            user.save(update_fields=["first_name", "last_name"])

        profile = getattr(user, "profile_or_none", None)
        if profile and not profile.title:
            job_title = self._extract_job_title(sociallogin)
            if job_title:
                profile.title = job_title
                profile.save(update_fields=["title"])
