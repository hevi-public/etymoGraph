# Deployment Guide

This guide covers deploying Etymology Explorer to production. Choose the option that best fits your needs and budget.

## Prerequisites

All deployment options require:
- Git repository (GitHub/GitLab)
- The Kaikki data loaded (~7.2 GB MongoDB database)
- Environment variables configured

## Option 1: DigitalOcean VPS (Recommended for Cost)

**Cost**: $24-48/month
**Difficulty**: Moderate
**Best for**: Personal projects, full control, learning

### Step 1: Create Droplet

1. Sign up at [DigitalOcean](https://www.digitalocean.com)
2. Create a new Droplet:
   - **Image**: Ubuntu 24.04 LTS
   - **Plan**: Basic (Shared CPU)
   - **Size**: 4 GB RAM / 2 CPUs / 80 GB SSD ($24/mo)
     - Or 8 GB RAM for better performance ($48/mo)
   - **Region**: Choose closest to your users
   - **Authentication**: SSH key (recommended) or password
   - **Hostname**: etymo-graph

3. Note your droplet's IP address

### Step 2: Initial Server Setup

SSH into your droplet:
```bash
ssh root@YOUR_DROPLET_IP
```

Update system and install dependencies:
```bash
# Update packages
apt update && apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Install Docker Compose
apt install docker-compose-plugin -y

# Install Git
apt install git -y

# Create non-root user (recommended)
adduser etymo
usermod -aG sudo etymo
usermod -aG docker etymo

# Switch to new user
su - etymo
```

### Step 3: Clone and Setup Project

```bash
# Clone repository
git clone https://github.com/YOUR_USERNAME/etymoGraph.git
cd etymoGraph

# Create .env file
cp .env.example .env
nano .env  # Edit if needed

# Setup project (downloads data + loads MongoDB)
make setup
```

**Note**: `make setup` will:
- Build Docker images
- Download Kaikki data (~2-3 GB compressed)
- Load into MongoDB (~20-30 minutes)

### Step 4: Configure Production Settings

Edit docker-compose for production:
```bash
nano docker-compose.yml
```

Remove development settings:
- Remove volume mounts (lines 10, 39) for read-only deployment
- Change backend CMD to production mode (remove `--reload`):
  ```yaml
  CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
  ```

Rebuild after changes:
```bash
docker compose build
make run
```

### Step 5: Configure Firewall

```bash
# Enable UFW firewall
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS (for later)
sudo ufw enable

# Check status
sudo ufw status
```

### Step 6: Setup Nginx Reverse Proxy (Optional but Recommended)

Install Nginx on host to handle domain + SSL:
```bash
sudo apt install nginx certbot python3-certbot-nginx -y

# Create Nginx config
sudo nano /etc/nginx/sites-available/etymo-graph
```

Add configuration:
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable and restart:
```bash
sudo ln -s /etc/nginx/sites-available/etymo-graph /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### Step 7: Setup SSL with Let's Encrypt

```bash
sudo certbot --nginx -d your-domain.com
```

Follow prompts to configure HTTPS.

### Step 8: Setup Auto-restart (Optional)

Create systemd service for auto-restart on reboot:
```bash
sudo nano /etc/systemd/system/etymo-graph.service
```

Add:
```ini
[Unit]
Description=Etymology Explorer
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/home/etymo/etymoGraph
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
User=etymo

[Install]
WantedBy=multi-user.target
```

Enable:
```bash
sudo systemctl enable etymo-graph
sudo systemctl start etymo-graph
```

### Monitoring & Maintenance

```bash
# View logs
make logs

# Check container status
docker compose ps

# Update application
cd ~/etymoGraph
git pull
docker compose build
docker compose up -d

# Backup MongoDB
docker compose exec mongodb mongodump --out /data/backup
```

---

## Option 2: Railway (Easiest)

**Cost**: ~$20-40/month
**Difficulty**: Easy
**Best for**: Quick deployment, automatic scaling

### Prerequisites

1. Create account at [Railway.app](https://railway.app)
2. Install Railway CLI:
   ```bash
   npm i -g @railway/cli
   railway login
   ```

### Step 1: Prepare Project

Railway doesn't support docker-compose directly. You'll need to deploy services separately:

Create `railway.json` in project root:
```json
{
  "build": {
    "builder": "DOCKERFILE",
    "dockerfilePath": "backend/Dockerfile"
  },
  "deploy": {
    "startCommand": "uvicorn app.main:app --host 0.0.0.0 --port $PORT",
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

### Step 2: Deploy MongoDB

```bash
railway init
railway add  # Select MongoDB plugin
```

This creates a managed MongoDB instance. Note the connection string from Railway dashboard.

### Step 3: Deploy Backend

```bash
# Create backend service
railway up

# Set environment variables in Railway dashboard
# MONGO_URI=mongodb://[railway-provided-url]/etymology
```

### Step 4: Deploy Frontend

Since Railway charges per service, consider:

**Option A**: Serve frontend from backend (recommended)
- Modify backend Dockerfile to include Nginx
- Single service = lower cost

**Option B**: Use free CDN
- Deploy static files to Vercel/Netlify (free)
- Point to Railway backend API

### Step 5: Load Data

You'll need to load Kaikki data manually:
1. Download data locally
2. Use `mongorestore` with Railway's MongoDB connection string
3. Or: Use a temporary Railway workspace just for loading, then export/import

**Note**: Uploading 7GB over network takes time (1-2 hours depending on connection).

---

## Option 3: Fly.io + MongoDB Atlas

**Cost**: ~$60-70/month
**Difficulty**: Moderate
**Best for**: Production apps, managed database

### Step 1: Setup MongoDB Atlas

1. Create account at [MongoDB Atlas](https://www.mongodb.com/cloud/atlas)
2. Create cluster:
   - **Tier**: M10 Dedicated ($57/mo)
   - **Region**: Match Fly.io region for low latency
   - **Storage**: 10 GB
3. Create database user
4. Whitelist Fly.io IPs (or 0.0.0.0/0 for all)
5. Note connection string: `mongodb+srv://user:pass@cluster.mongodb.net/etymology`

### Step 2: Load Data to Atlas

From local machine:
```bash
# Export local MongoDB
docker compose exec mongodb mongodump --out /data/backup

# Import to Atlas (from host)
mongorestore --uri "mongodb+srv://user:pass@cluster.mongodb.net/etymology" data/backup/etymology
```

This will take 1-2 hours depending on upload speed.

### Step 3: Setup Fly.io

Install Fly CLI:
```bash
curl -L https://fly.io/install.sh | sh
fly auth login
```

### Step 4: Create Fly Apps

**Deploy Backend**:
```bash
cd backend
fly launch --name etymo-backend --region sjc

# Set MongoDB connection
fly secrets set MONGO_URI="mongodb+srv://user:pass@cluster.mongodb.net/etymology"

# Deploy
fly deploy
```

**Deploy Frontend**:
```bash
cd ../frontend
fly launch --name etymo-frontend --region sjc

# Update nginx.conf to proxy /api/ to etymo-backend.fly.dev
# Then deploy
fly deploy
```

### Step 5: Custom Domain (Optional)

```bash
fly domains add your-domain.com
# Follow DNS instructions
fly certs create your-domain.com
```

---

## Option 4: Docker Compose on Any VPS

Works on **AWS EC2**, **Linode**, **Hetzner**, **Vultr**, etc.

Same process as DigitalOcean (Option 1), but:
1. Choose instance type with 4-8 GB RAM
2. Install Docker + Docker Compose
3. Clone repo and run `make setup`

---

## Data Migration Strategies

### Moving Existing MongoDB to Cloud

**From local to Atlas/Cloud**:
```bash
# Export
docker compose exec mongodb mongodump --out /data/backup

# Import to cloud (use cloud connection string)
mongorestore --uri "CLOUD_CONNECTION_STRING" ./data/backup/etymology
```

**From cloud to VPS**:
```bash
# Export from cloud
mongodump --uri "CLOUD_CONNECTION_STRING" --out ./backup

# Import to VPS
scp -r backup root@VPS_IP:/tmp/
ssh root@VPS_IP
cd ~/etymoGraph
docker compose exec -T mongodb mongorestore --drop /tmp/backup/etymology
```

---

## Environment Variables

Create `.env` file (all deployments):
```bash
# MongoDB
MONGO_URI=mongodb://mongodb:27017/etymology  # Adjust for cloud

# Backend (optional)
LOG_LEVEL=info
```

---

## Troubleshooting

### MongoDB out of memory
- Increase RAM (VPS) or upgrade tier (Atlas)
- MongoDB working set needs ~2-4 GB RAM

### Slow data loading
- Normal: 20-30 minutes for 10.4M documents
- Use `make logs` to monitor progress

### Containers won't start
```bash
docker compose down
docker compose up -d
make logs  # Check error messages
```

### Port conflicts
Edit `docker-compose.yml` to change ports:
```yaml
ports:
  - "8081:80"  # Change 8080 to 8081
```

---

## Cost Comparison Summary

| Option | Monthly Cost | Setup Time | Maintenance |
|--------|--------------|------------|-------------|
| DigitalOcean VPS | $24-48 | 1-2 hours | Manual updates |
| Railway | $20-40 | 30 min | Automatic |
| Fly.io + Atlas | $60-70 | 1 hour | Automatic |
| AWS/Linode VPS | $20-60 | 1-2 hours | Manual updates |

---

## Next Steps After Deployment

1. **Monitor performance**: Use `docker stats` or cloud dashboards
2. **Setup backups**: Regular MongoDB exports
3. **Add monitoring**: Consider Uptime Robot, Pingdom
4. **Enable HTTPS**: Use Let's Encrypt (free)
5. **Add analytics**: Google Analytics, Plausible, etc.
6. **Optimize**: Add Redis cache if needed (future enhancement)
