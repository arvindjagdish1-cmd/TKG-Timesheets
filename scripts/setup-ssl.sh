#!/bin/bash
set -e

# TKG Time & Expense - SSL Certificate Setup
# Run this ONCE after initial deployment to get Let's Encrypt certificates

echo "======================================"
echo "TKG Time & Expense - SSL Setup"
echo "======================================"

cd "$(dirname "$0")/.."

DOMAIN="tkgtimesheets.com"
EMAIL="admin@thekeystonegroup.com"  # Change this to your email

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo ""
echo -e "${YELLOW}This script will obtain SSL certificates from Let's Encrypt.${NC}"
echo -e "${YELLOW}Make sure your domain ($DOMAIN) is pointing to this server!${NC}"
echo ""
read -p "Press Enter to continue or Ctrl+C to cancel..."

# Step 1: Use initial nginx config (HTTP only)
echo ""
echo -e "${GREEN}Step 1: Setting up initial nginx config (HTTP only)...${NC}"
cp docker/nginx/nginx-initial.conf docker/nginx/nginx.conf

# Step 2: Build and start with HTTP-only config
echo ""
echo -e "${GREEN}Step 2: Starting services...${NC}"
docker compose -f compose.prod.yml up -d

# Wait for nginx to start
sleep 5

# Step 3: Get SSL certificate
echo ""
echo -e "${GREEN}Step 3: Obtaining SSL certificate from Let's Encrypt...${NC}"
docker compose -f compose.prod.yml run --rm certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email $EMAIL \
    --agree-tos \
    --no-eff-email \
    -d $DOMAIN \
    -d www.$DOMAIN

# Step 4: Update nginx config to use SSL
echo ""
echo -e "${GREEN}Step 4: Updating nginx to use SSL...${NC}"
cat > docker/nginx/nginx.conf << 'NGINX_CONF'
upstream django {
    server web:8000;
}

server {
    listen 80;
    server_name tkgtimesheets.com www.tkgtimesheets.com;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://$host$request_uri;
    }
}

server {
    listen 443 ssl http2;
    server_name tkgtimesheets.com www.tkgtimesheets.com;

    ssl_certificate /etc/letsencrypt/live/tkgtimesheets.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/tkgtimesheets.com/privkey.pem;

    ssl_session_timeout 1d;
    ssl_session_cache shared:SSL:50m;
    ssl_session_tickets off;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;

    add_header Strict-Transport-Security "max-age=63072000" always;
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;

    client_max_body_size 20M;

    location /static/ {
        alias /app/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location /media/ {
        alias /app/media/;
        expires 7d;
    }

    location / {
        proxy_pass http://django;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
        proxy_connect_timeout 300;
        proxy_send_timeout 300;
        proxy_read_timeout 300;
    }
}
NGINX_CONF

# Step 5: Rebuild and restart nginx
echo ""
echo -e "${GREEN}Step 5: Restarting nginx with SSL...${NC}"
docker compose -f compose.prod.yml build nginx
docker compose -f compose.prod.yml up -d nginx

echo ""
echo "======================================"
echo -e "${GREEN}SSL Setup complete!${NC}"
echo "======================================"
echo ""
echo "Your site is now available at:"
echo "  https://tkgtimesheets.com"
echo ""
echo "SSL certificates will auto-renew via certbot."
echo ""
