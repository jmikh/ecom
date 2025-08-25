#!/bin/bash

# PostgreSQL Database Setup Script
# This script creates the necessary database and user for the Product Search Assistant

set -e  # Exit on any error

echo "🚀 Setting up PostgreSQL database for Product Search Assistant..."

# Load environment variables if .env exists
if [ -f .env ]; then
    echo "📄 Loading environment variables from .env file..."
    export $(grep -v '^#' .env | xargs)
fi

# Set default values if not provided in .env
DB_HOST=${DB_HOST:-localhost}
DB_PORT=${DB_PORT:-5432}
DB_USER=${DB_USER:-$(whoami)}
DB_PASSWORD=${DB_PASSWORD:-}
DB_NAME=${DB_NAME:-ecom_products}
SUPERUSER=${POSTGRES_SUPERUSER:-postgres}

echo "📋 Database configuration:"
echo "  Host: $DB_HOST"
echo "  Port: $DB_PORT"
echo "  Database: $DB_NAME"
echo "  User: $DB_USER"
echo ""

# Check if PostgreSQL is running
echo "🔍 Checking PostgreSQL service status..."
if ! pg_isready -h $DB_HOST -p $DB_PORT > /dev/null 2>&1; then
    echo "❌ PostgreSQL is not running on $DB_HOST:$DB_PORT"
    echo "   Please start PostgreSQL first:"
    echo "   macOS (Homebrew): brew services start postgresql@14"
    echo "   Linux (systemd): sudo systemctl start postgresql"
    echo "   Docker: docker run --name postgres -e POSTGRES_PASSWORD=mypassword -d -p 5432:5432 postgres"
    exit 1
fi

echo "✅ PostgreSQL is running"

# Function to run psql commands
run_psql() {
    local cmd="$1"
    local db="${2:-postgres}"
    local user="${3:-$SUPERUSER}"
    
    if [ -n "$DB_PASSWORD" ] && [ "$user" = "$DB_USER" ]; then
        PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$user" -d "$db" -c "$cmd"
    else
        psql -h "$DB_HOST" -p "$DB_PORT" -U "$user" -d "$db" -c "$cmd"
    fi
}

# Try connecting as the current user first (for Homebrew installs)
echo "🔗 Testing connection as current user ($DB_USER)..."
if psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d postgres -c "SELECT version();" > /dev/null 2>&1; then
    SUPERUSER=$DB_USER
    echo "✅ Connected as $DB_USER"
elif psql -h $DB_HOST -p $DB_PORT -U postgres -d postgres -c "SELECT version();" > /dev/null 2>&1; then
    SUPERUSER=postgres
    echo "✅ Connected as postgres superuser"
else
    echo "❌ Cannot connect to PostgreSQL"
    echo "   Try one of these:"
    echo "   1. createdb (if using Homebrew install)"
    echo "   2. sudo -u postgres psql (if using system install)"
    echo "   3. Check your PostgreSQL authentication configuration"
    exit 1
fi

# Create database user if it doesn't exist (only if not already the superuser)
if [ "$SUPERUSER" != "$DB_USER" ]; then
    echo "👤 Creating database user '$DB_USER'..."
    
    # Check if user exists
    user_exists=$(run_psql "SELECT 1 FROM pg_user WHERE usename = '$DB_USER';" postgres $SUPERUSER | grep -c "1" || echo "0")
    
    if [ "$user_exists" = "0" ]; then
        if [ -n "$DB_PASSWORD" ]; then
            run_psql "CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';" postgres $SUPERUSER
        else
            run_psql "CREATE USER $DB_USER;" postgres $SUPERUSER
        fi
        echo "✅ User '$DB_USER' created"
    else
        echo "ℹ️  User '$DB_USER' already exists"
    fi
    
    # Grant necessary privileges
    run_psql "ALTER USER $DB_USER CREATEDB;" postgres $SUPERUSER
fi

# Create database if it doesn't exist
echo "🗄️  Creating database '$DB_NAME'..."

# Check if database exists
db_exists=$(run_psql "SELECT 1 FROM pg_database WHERE datname = '$DB_NAME';" postgres $SUPERUSER | grep -c "1" || echo "0")

if [ "$db_exists" = "0" ]; then
    run_psql "CREATE DATABASE $DB_NAME OWNER $DB_USER;" postgres $SUPERUSER
    echo "✅ Database '$DB_NAME' created"
else
    echo "ℹ️  Database '$DB_NAME' already exists"
fi

# Enable pgvector extension
echo "🧮 Enabling pgvector extension..."
run_psql "CREATE EXTENSION IF NOT EXISTS vector;" $DB_NAME $DB_USER

echo ""
echo "🎉 Database setup complete!"
echo ""
echo "📝 Connection details:"
echo "  Database URL: postgresql://$DB_USER@$DB_HOST:$DB_PORT/$DB_NAME"
echo ""
echo "🔧 Next steps:"
echo "  1. Update your .env file with the database credentials"
echo "  2. Run: python src/database/setup.py"
echo "  3. Run: python src/pipeline/ingest.py"
echo ""