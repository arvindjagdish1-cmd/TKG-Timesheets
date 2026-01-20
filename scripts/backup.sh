#!/bin/bash
set -e

# TKG Time & Expense - Backup Script
# Run this regularly (e.g., daily via cron)

echo "======================================"
echo "TKG Time & Expense - Backup"
echo "======================================"

cd "$(dirname "$0")/.."

BACKUP_DIR="./backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR

GREEN='\033[0;32m'
NC='\033[0m'

# Backup database
echo ""
echo -e "${GREEN}Backing up database...${NC}"
docker compose -f compose.prod.yml exec -T db pg_dump -U tkg_te tkg_te > "$BACKUP_DIR/db_backup_$TIMESTAMP.sql"
gzip "$BACKUP_DIR/db_backup_$TIMESTAMP.sql"
echo "Database backed up to: $BACKUP_DIR/db_backup_$TIMESTAMP.sql.gz"

# Backup media files
echo ""
echo -e "${GREEN}Backing up media files (receipts)...${NC}"
docker compose -f compose.prod.yml run --rm -v $(pwd)/$BACKUP_DIR:/backup web \
    tar -czf /backup/media_backup_$TIMESTAMP.tar.gz -C /app media
echo "Media backed up to: $BACKUP_DIR/media_backup_$TIMESTAMP.tar.gz"

# Backup exports
echo ""
echo -e "${GREEN}Backing up export files...${NC}"
docker compose -f compose.prod.yml run --rm -v $(pwd)/$BACKUP_DIR:/backup web \
    tar -czf /backup/exports_backup_$TIMESTAMP.tar.gz -C /app exports
echo "Exports backed up to: $BACKUP_DIR/exports_backup_$TIMESTAMP.tar.gz"

# Clean up old backups (keep last 30 days)
echo ""
echo -e "${GREEN}Cleaning up old backups (keeping last 30 days)...${NC}"
find $BACKUP_DIR -type f -mtime +30 -delete

echo ""
echo "======================================"
echo -e "${GREEN}Backup complete!${NC}"
echo "======================================"
echo ""
echo "Backup files are in: $BACKUP_DIR"
ls -la $BACKUP_DIR
echo ""
