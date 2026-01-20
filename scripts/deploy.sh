#!/bin/bash
set -e

# TKG Time & Expense - Production Deployment Script
# Run this on your production server

echo "======================================"
echo "TKG Time & Expense - Deployment"
echo "======================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo -e "${YELLOW}Warning: Running as root. Consider using a non-root user with docker permissions.${NC}"
fi

# Check Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed${NC}"
    exit 1
fi

if ! command -v docker compose &> /dev/null; then
    echo -e "${RED}Error: Docker Compose is not installed${NC}"
    exit 1
fi

# Navigate to app directory
cd "$(dirname "$0")/.."

echo ""
echo -e "${GREEN}Step 1: Pulling latest code...${NC}"
git pull origin main 2>/dev/null || echo "Skipping git pull (not a git repo or no remote)"

echo ""
echo -e "${GREEN}Step 2: Building containers...${NC}"
docker compose -f compose.prod.yml build

echo ""
echo -e "${GREEN}Step 3: Starting database and redis...${NC}"
docker compose -f compose.prod.yml up -d db redis
sleep 5

echo ""
echo -e "${GREEN}Step 4: Running migrations...${NC}"
docker compose -f compose.prod.yml run --rm web python manage.py migrate

echo ""
echo -e "${GREEN}Step 5: Collecting static files...${NC}"
docker compose -f compose.prod.yml run --rm web python manage.py collectstatic --noinput

echo ""
echo -e "${GREEN}Step 6: Starting all services...${NC}"
docker compose -f compose.prod.yml up -d

echo ""
echo -e "${GREEN}Step 7: Checking service health...${NC}"
sleep 10
docker compose -f compose.prod.yml ps

echo ""
echo "======================================"
echo -e "${GREEN}Deployment complete!${NC}"
echo "======================================"
echo ""
echo "Your app should now be running at:"
echo "  - http://tkgtimesheets.com (redirects to HTTPS)"
echo "  - https://tkgtimesheets.com"
echo ""
echo "To view logs: docker compose -f compose.prod.yml logs -f"
echo "To stop: docker compose -f compose.prod.yml down"
echo ""
