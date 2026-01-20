# TKG Time & Expense - Production Deployment Guide

This guide covers deploying the TKG Time & Expense Portal to a production server.

## Prerequisites

### Server Requirements
- **OS**: Ubuntu 22.04 LTS (recommended) or similar Linux
- **RAM**: Minimum 2GB, recommended 4GB
- **Storage**: 20GB+ (for receipts and exports)
- **Ports**: 80 (HTTP), 443 (HTTPS) open

### Software Requirements
- Docker Engine 24+
- Docker Compose v2+
- Git

### DNS Configuration
Point your domain to your server:
```
tkgtimesheets.com     A     <your-server-ip>
www.tkgtimesheets.com A     <your-server-ip>
```

---

## Quick Deployment (3 Steps)

### Step 1: Clone and Configure

```bash
# Clone the repository
git clone <your-repo-url> /opt/tkg-timesheets
cd /opt/tkg-timesheets

# The .env.prod file is already configured with your credentials
# Review it if needed:
cat .env.prod
```

### Step 2: Deploy

```bash
# Run the deployment script
./scripts/deploy.sh
```

### Step 3: Set Up SSL

```bash
# Get SSL certificate from Let's Encrypt
./scripts/setup-ssl.sh
```

### Step 4: Initialize Data

```bash
# Create admin user and load initial data
./scripts/init-data.sh
```

**Done!** Your app is now live at https://tkgtimesheets.com

---

## Detailed Deployment Steps

### 1. Server Setup (Ubuntu)

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER

# Install Docker Compose
sudo apt install docker-compose-plugin

# Log out and back in for group changes
```

### 2. Clone Repository

```bash
cd /opt
sudo git clone <your-repo-url> tkg-timesheets
sudo chown -R $USER:$USER tkg-timesheets
cd tkg-timesheets
```

### 3. Configure Environment

The `.env.prod` file is pre-configured with:
- ✅ Microsoft OAuth credentials
- ✅ Domain restrictions (thekeystonegroup.com only)
- ✅ Secure database password
- ✅ Secret key

### 4. Build and Deploy

```bash
# Build containers
docker compose -f compose.prod.yml build

# Start services
docker compose -f compose.prod.yml up -d
```

### 5. Get SSL Certificate

```bash
# Ensure DNS is pointing to this server, then:
./scripts/setup-ssl.sh

# Follow the prompts
```

### 6. Initialize Database

```bash
# Run migrations
docker compose -f compose.prod.yml run --rm web python manage.py migrate

# Create groups and permissions
docker compose -f compose.prod.yml run --rm web python manage.py seed_roles

# Load charge codes and expense categories
docker compose -f compose.prod.yml run --rm web python manage.py seed_reference_data

# Create periods for current month
docker compose -f compose.prod.yml run --rm web python manage.py create_periods --year 2026 --month 1

# Create admin user
docker compose -f compose.prod.yml run --rm web python manage.py createsuperuser
```

---

## Post-Deployment Configuration

### Microsoft Entra ID

Ensure these redirect URIs are configured in your Microsoft Entra app registration:

```
https://tkgtimesheets.com/accounts/microsoft/login/callback/
```

### Assign User Roles

1. Log in to https://tkgtimesheets.com/admin
2. Go to **Users** section
3. Select a user
4. Assign to groups:
   - `employees` - Regular employees
   - `office_manager` - Can review/approve and export
   - `managing_partner` - Read-only review access
   - `payroll_partner` - Download exports only
   - `accountants` - Download expense exports

### Create Future Periods

Run monthly to create new timesheet/expense periods:

```bash
# Create periods for a specific month
docker compose -f compose.prod.yml run --rm web python manage.py create_periods --year 2026 --month 2
```

---

## Management Commands

### View Logs

```bash
# All services
docker compose -f compose.prod.yml logs -f

# Specific service
docker compose -f compose.prod.yml logs -f web
docker compose -f compose.prod.yml logs -f worker
docker compose -f compose.prod.yml logs -f nginx
```

### Restart Services

```bash
# Restart everything
docker compose -f compose.prod.yml restart

# Restart specific service
docker compose -f compose.prod.yml restart web
```

### Stop Services

```bash
docker compose -f compose.prod.yml down
```

### Database Access

```bash
# Connect to database
docker compose -f compose.prod.yml exec db psql -U tkg_te tkg_te
```

### Run Django Management Commands

```bash
docker compose -f compose.prod.yml run --rm web python manage.py <command>
```

---

## Backups

### Manual Backup

```bash
./scripts/backup.sh
```

### Automated Daily Backups (Cron)

```bash
# Edit crontab
crontab -e

# Add this line (runs at 2 AM daily):
0 2 * * * /opt/tkg-timesheets/scripts/backup.sh >> /var/log/tkg-backup.log 2>&1
```

### Restore from Backup

```bash
# Restore database
gunzip -c backups/db_backup_TIMESTAMP.sql.gz | \
  docker compose -f compose.prod.yml exec -T db psql -U tkg_te tkg_te

# Restore media files
docker compose -f compose.prod.yml run --rm -v $(pwd)/backups:/backup web \
  tar -xzf /backup/media_backup_TIMESTAMP.tar.gz -C /app
```

---

## Updating the Application

```bash
cd /opt/tkg-timesheets

# Pull latest code
git pull origin main

# Rebuild and restart
docker compose -f compose.prod.yml build
docker compose -f compose.prod.yml up -d

# Run any new migrations
docker compose -f compose.prod.yml run --rm web python manage.py migrate
```

---

## Troubleshooting

### SSL Certificate Issues

```bash
# Check certificate status
docker compose -f compose.prod.yml run --rm certbot certificates

# Force renewal
docker compose -f compose.prod.yml run --rm certbot renew --force-renewal
docker compose -f compose.prod.yml restart nginx
```

### 502 Bad Gateway

```bash
# Check if web container is running
docker compose -f compose.prod.yml ps

# Check web logs
docker compose -f compose.prod.yml logs web

# Restart web
docker compose -f compose.prod.yml restart web
```

### Database Connection Issues

```bash
# Check database is running
docker compose -f compose.prod.yml ps db

# Test connection
docker compose -f compose.prod.yml exec db pg_isready -U tkg_te
```

### OAuth Login Issues

1. Verify redirect URI in Microsoft Entra matches exactly
2. Check that user's email domain is `@thekeystonegroup.com`
3. Check logs for specific error:
   ```bash
   docker compose -f compose.prod.yml logs web | grep -i oauth
   ```

---

## Security Notes

- ✅ HTTPS enforced (automatic redirect)
- ✅ HSTS enabled (1 year)
- ✅ Secure cookies in production
- ✅ Domain-restricted login (thekeystonegroup.com only)
- ✅ Tenant ID validation (your Azure AD only)
- ✅ Database not exposed to internet
- ✅ Redis not exposed to internet

### Recommended: Firewall

```bash
# UFW setup
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

---

## Support

For issues or questions, contact your system administrator.
