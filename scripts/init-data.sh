#!/bin/bash
set -e

# TKG Time & Expense - Initialize Data
# Run this ONCE after first deployment

echo "======================================"
echo "TKG Time & Expense - Data Initialization"
echo "======================================"

cd "$(dirname "$0")/.."

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo ""
echo -e "${GREEN}Step 1: Running database migrations...${NC}"
docker compose -f compose.prod.yml run --rm web python manage.py migrate

echo ""
echo -e "${GREEN}Step 2: Creating role groups and permissions...${NC}"
docker compose -f compose.prod.yml run --rm web python manage.py seed_roles

echo ""
echo -e "${GREEN}Step 3: Loading charge codes and expense categories...${NC}"
docker compose -f compose.prod.yml run --rm web python manage.py seed_reference_data

echo ""
echo -e "${GREEN}Step 4: Creating periods for current month...${NC}"
YEAR=$(date +%Y)
MONTH=$(date +%m)
docker compose -f compose.prod.yml run --rm web python manage.py create_periods --year $YEAR --month $MONTH

echo ""
echo -e "${YELLOW}Step 5: Create your admin superuser${NC}"
echo "You'll be prompted to enter email and password:"
docker compose -f compose.prod.yml run --rm web python manage.py createsuperuser

echo ""
echo "======================================"
echo -e "${GREEN}Data initialization complete!${NC}"
echo "======================================"
echo ""
echo "You can now log in at https://tkgtimesheets.com"
echo ""
echo "First-time setup:"
echo "1. Log in with your Microsoft account (@thekeystonegroup.com)"
echo "2. Your admin can assign users to roles via /admin"
echo ""
