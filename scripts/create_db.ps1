# PostgreSQL Database Setup Script for Windows
# This script creates the necessary database and user for the Product Search Assistant

param(
    [string]$DBHost = "localhost",
    [string]$DBPort = "5432", 
    [string]$DBUser = $env:USERNAME,
    [string]$DBPassword = "",
    [string]$DBName = "ecom_products",
    [string]$SuperUser = "postgres"
)

Write-Host "🚀 Setting up PostgreSQL database for Product Search Assistant..." -ForegroundColor Green

# Load environment variables from .env if it exists
if (Test-Path ".env") {
    Write-Host "📄 Loading environment variables from .env file..." -ForegroundColor Yellow
    Get-Content ".env" | ForEach-Object {
        if ($_ -match "^([^#][^=]*)=(.*)$") {
            Set-Variable -Name $matches[1] -Value $matches[2] -Scope Global
        }
    }
}

# Override with loaded env vars if they exist
if ($env:DB_HOST) { $DBHost = $env:DB_HOST }
if ($env:DB_PORT) { $DBPort = $env:DB_PORT }
if ($env:DB_USER) { $DBUser = $env:DB_USER }
if ($env:DB_PASSWORD) { $DBPassword = $env:DB_PASSWORD }
if ($env:DB_NAME) { $DBName = $env:DB_NAME }

Write-Host "📋 Database configuration:" -ForegroundColor Cyan
Write-Host "  Host: $DBHost"
Write-Host "  Port: $DBPort"
Write-Host "  Database: $DBName"
Write-Host "  User: $DBUser"
Write-Host ""

# Check if PostgreSQL is running
Write-Host "🔍 Checking PostgreSQL service status..." -ForegroundColor Yellow
try {
    $null = & pg_isready -h $DBHost -p $DBPort
    Write-Host "✅ PostgreSQL is running" -ForegroundColor Green
} catch {
    Write-Host "❌ PostgreSQL is not running on ${DBHost}:${DBPort}" -ForegroundColor Red
    Write-Host "   Please start PostgreSQL first:" -ForegroundColor Yellow
    Write-Host "   Windows: net start postgresql-x64-14" -ForegroundColor Gray
    Write-Host "   Docker: docker run --name postgres -e POSTGRES_PASSWORD=mypassword -d -p 5432:5432 postgres" -ForegroundColor Gray
    exit 1
}

# Function to run psql commands
function Invoke-PSQL {
    param(
        [string]$Command,
        [string]$Database = "postgres",
        [string]$User = $SuperUser
    )
    
    $env:PGPASSWORD = if ($User -eq $DBUser -and $DBPassword) { $DBPassword } else { $null }
    
    try {
        $result = & psql -h $DBHost -p $DBPort -U $User -d $Database -c $Command -t -A
        return $result
    } catch {
        throw "Failed to execute SQL: $Command"
    }
}

# Test connection
Write-Host "🔗 Testing connection..." -ForegroundColor Yellow
try {
    Invoke-PSQL "SELECT version();" "postgres" $DBUser | Out-Null
    $SuperUser = $DBUser
    Write-Host "✅ Connected as $DBUser" -ForegroundColor Green
} catch {
    try {
        Invoke-PSQL "SELECT version();" "postgres" "postgres" | Out-Null
        $SuperUser = "postgres"
        Write-Host "✅ Connected as postgres superuser" -ForegroundColor Green
    } catch {
        Write-Host "❌ Cannot connect to PostgreSQL" -ForegroundColor Red
        Write-Host "   Check your PostgreSQL installation and authentication" -ForegroundColor Yellow
        exit 1
    }
}

# Create database user if needed
if ($SuperUser -ne $DBUser) {
    Write-Host "👤 Creating database user '$DBUser'..." -ForegroundColor Yellow
    
    $userExists = Invoke-PSQL "SELECT 1 FROM pg_user WHERE usename = '$DBUser';" "postgres" $SuperUser
    
    if (-not $userExists) {
        if ($DBPassword) {
            Invoke-PSQL "CREATE USER $DBUser WITH PASSWORD '$DBPassword';" "postgres" $SuperUser
        } else {
            Invoke-PSQL "CREATE USER $DBUser;" "postgres" $SuperUser
        }
        Write-Host "✅ User '$DBUser' created" -ForegroundColor Green
    } else {
        Write-Host "ℹ️  User '$DBUser' already exists" -ForegroundColor Blue
    }
    
    Invoke-PSQL "ALTER USER $DBUser CREATEDB;" "postgres" $SuperUser
}

# Create database
Write-Host "🗄️  Creating database '$DBName'..." -ForegroundColor Yellow

$dbExists = Invoke-PSQL "SELECT 1 FROM pg_database WHERE datname = '$DBName';" "postgres" $SuperUser

if (-not $dbExists) {
    Invoke-PSQL "CREATE DATABASE $DBName OWNER $DBUser;" "postgres" $SuperUser
    Write-Host "✅ Database '$DBName' created" -ForegroundColor Green
} else {
    Write-Host "ℹ️  Database '$DBName' already exists" -ForegroundColor Blue
}

# Enable pgvector extension
Write-Host "🧮 Enabling pgvector extension..." -ForegroundColor Yellow
Invoke-PSQL "CREATE EXTENSION IF NOT EXISTS vector;" $DBName $DBUser

Write-Host ""
Write-Host "🎉 Database setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "📝 Connection details:" -ForegroundColor Cyan
Write-Host "  Database URL: postgresql://$DBUser@${DBHost}:${DBPort}/$DBName"
Write-Host ""
Write-Host "🔧 Next steps:" -ForegroundColor Yellow
Write-Host "  1. Update your .env file with the database credentials"
Write-Host "  2. Run: python src/database/setup.py"
Write-Host "  3. Run: python src/pipeline/ingest.py"
Write-Host ""