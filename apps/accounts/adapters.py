import logging

from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.contrib.auth import get_user_model

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
        if not User.objects.filter(email=email, is_active=True).exists():
            logger.warning("Microsoft login blocked: %s not on roster.", email)
            raise PermissionDenied("This account is not on the approved roster.")

        # Normalize stored email
        sociallogin.user.email = email

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
