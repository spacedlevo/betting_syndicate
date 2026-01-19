# Deploying on Proxmox

This guide covers setting up the Betting Syndicate application on a Proxmox virtual machine accessible from your local network.

---

## Part 1: Create the Virtual Machine in Proxmox

### 1.1 Download Ubuntu Server ISO

1. On your local machine, download Ubuntu Server 24.04 LTS:
   - https://ubuntu.com/download/server

2. Upload the ISO to Proxmox:
   - Log into Proxmox web interface (usually `https://your-proxmox-ip:8006`)
   - Select your storage (e.g., `local`)
   - Click **ISO Images** → **Upload**
   - Select the Ubuntu ISO and upload

### 1.2 Create the VM

1. Click **Create VM** (top right)

2. **General tab:**
   - Node: Select your Proxmox node
   - VM ID: Auto-assigned or choose one (e.g., `100`)
   - Name: `betting-syndicate`

3. **OS tab:**
   - ISO image: Select the Ubuntu Server ISO you uploaded
   - Type: `Linux`
   - Version: `6.x - 2.6 Kernel`

4. **System tab:**
   - Machine: `q35`
   - BIOS: `OVMF (UEFI)` or `SeaBIOS` (either works)
   - Add EFI Disk if using UEFI
   - Qemu Agent: ✓ Enable

5. **Disks tab:**
   - Bus/Device: `VirtIO Block`
   - Storage: Select your storage
   - Disk size: `20 GB` (minimum, 32GB recommended)

6. **CPU tab:**
   - Cores: `2` (minimum)
   - Type: `host` (best performance) or `x86-64-v2-AES`

7. **Memory tab:**
   - Memory: `2048 MB` (2GB minimum, 4GB recommended)

8. **Network tab:**
   - Bridge: `vmbr0` (your network bridge)
   - Model: `VirtIO (paravirtualized)`

9. Click **Finish** to create the VM

---

## Part 2: Install Ubuntu Server

### 2.1 Start Installation

1. Select the VM in Proxmox
2. Click **Start**
3. Click **Console** to open the terminal

### 2.2 Ubuntu Installation Steps

1. Select **Try or Install Ubuntu Server**

2. Select your language (English)

3. **Installer update:** Choose "Continue without updating"

4. **Keyboard:** Select your layout

5. **Installation type:** Ubuntu Server (minimized is fine too)

6. **Network:**
   - Should auto-configure via DHCP
   - Note the IP address shown (e.g., `192.168.1.50`)
   - Or configure a static IP (recommended for servers)

7. **Proxy:** Leave blank unless you use one

8. **Mirror:** Accept default

9. **Storage:** Use entire disk (default)

10. **Profile setup:**
    - Your name: `Admin`
    - Server name: `betting-syndicate`
    - Username: `admin` (or your preference)
    - Password: Choose a strong password

11. **Ubuntu Pro:** Skip for now

12. **SSH Setup:**
    - ✓ Install OpenSSH server
    - Import SSH identity: Optional

13. **Featured snaps:** Skip (press Tab to Done)

14. Wait for installation to complete

15. Select **Reboot Now**

16. Press Enter when prompted to remove installation media

---

## Part 3: Initial Server Setup

### 3.1 Connect via SSH

From your local machine:

```bash
ssh admin@192.168.1.50  # Replace with your VM's IP
```

### 3.2 Update the System

```bash
sudo apt update && sudo apt upgrade -y
```

### 3.3 Install Required Packages

```bash
sudo apt install -y python3 python3-pip python3-venv git nginx
```

### 3.4 Install QEMU Guest Agent (for Proxmox)

```bash
sudo apt install -y qemu-guest-agent
sudo systemctl enable qemu-guest-agent
sudo systemctl start qemu-guest-agent
```

---

## Part 4: Deploy the Application

### 4.1 Create Application Directory

```bash
sudo mkdir -p /opt/betting-syndicate
sudo chown $USER:$USER /opt/betting-syndicate
```

### 4.2 Transfer Application Files

**Option A: From your local machine using SCP**

```bash
# Run this from your local machine, in the project directory
scp -r ./* admin@192.168.1.50:/opt/betting-syndicate/
```

**Option B: Clone from Git (if you have a repo)**

```bash
cd /opt/betting-syndicate
git clone https://your-repo-url.git .
```

**Option C: Create a tar archive and transfer**

On your local machine:
```bash
cd /home/levo/Documents/projects
tar -czvf betting-syndicate.tar.gz betting_syndicate/
scp betting-syndicate.tar.gz admin@192.168.1.50:/opt/
```

On the server:
```bash
cd /opt
tar -xzvf betting-syndicate.tar.gz
mv betting_syndicate/* betting-syndicate/
rm -rf betting_syndicate betting-syndicate.tar.gz
```

### 4.3 Set Up Python Virtual Environment

```bash
cd /opt/betting-syndicate
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 4.4 Create Upload Directories

```bash
mkdir -p /opt/betting-syndicate/uploads/screenshots
```

### 4.5 Initialize the Database (if needed)

```bash
cd /opt/betting-syndicate
source venv/bin/activate
python -c "from app.database import engine, Base; Base.metadata.create_all(bind=engine)"
```

### 4.6 Test the Application

```bash
cd /opt/betting-syndicate
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Visit `http://192.168.1.50:8000` in your browser to verify it works.

Press `Ctrl+C` to stop.

---

## Part 5: Set Up as a System Service

### 5.1 Create Systemd Service File

```bash
sudo nano /etc/systemd/system/betting-syndicate.service
```

Paste the following:

```ini
[Unit]
Description=Betting Syndicate Web Application
After=network.target

[Service]
Type=simple
User=admin
Group=admin
WorkingDirectory=/opt/betting-syndicate
Environment="PATH=/opt/betting-syndicate/venv/bin"
ExecStart=/opt/betting-syndicate/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Press `Ctrl+X`, then `Y`, then `Enter` to save.

### 5.2 Enable and Start the Service

```bash
sudo systemctl daemon-reload
sudo systemctl enable betting-syndicate
sudo systemctl start betting-syndicate
```

### 5.3 Check Status

```bash
sudo systemctl status betting-syndicate
```

You should see "Active: active (running)".

---

## Part 6: Configure Nginx Reverse Proxy

### 6.1 Create Nginx Configuration

```bash
sudo nano /etc/nginx/sites-available/betting-syndicate
```

Paste the following:

```nginx
server {
    listen 80;
    server_name betting-syndicate.local betting.local 192.168.1.50;

    client_max_body_size 10M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /uploads {
        alias /opt/betting-syndicate/uploads;
    }
}
```

Replace `192.168.1.50` with your VM's actual IP address.

### 6.2 Enable the Site

```bash
sudo ln -s /etc/nginx/sites-available/betting-syndicate /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default  # Remove default site
sudo nginx -t  # Test configuration
sudo systemctl restart nginx
```

### 6.3 Allow Firewall (if enabled)

```bash
sudo ufw allow 'Nginx Full'
sudo ufw allow OpenSSH
sudo ufw enable
```

---

## Part 7: Configure Static IP (Recommended)

### 7.1 Find Your Network Interface

```bash
ip a
```

Look for your interface name (usually `ens18` or `eth0`).

### 7.2 Configure Netplan

```bash
sudo nano /etc/netplan/00-installer-config.yaml
```

Replace contents with:

```yaml
network:
  version: 2
  ethernets:
    ens18:  # Replace with your interface name
      dhcp4: no
      addresses:
        - 192.168.1.50/24  # Your desired static IP
      routes:
        - to: default
          via: 192.168.1.1  # Your router IP
      nameservers:
        addresses:
          - 8.8.8.8
          - 8.8.4.4
```

### 7.3 Apply Configuration

```bash
sudo netplan apply
```

---

## Part 8: Access from Your Network

### Option A: By IP Address

Simply visit `http://192.168.1.50` in your browser.

### Option B: Local DNS Name (Router)

1. Log into your router's admin panel
2. Find DHCP/DNS settings
3. Add a static lease or DNS entry:
   - Hostname: `betting` or `betting-syndicate`
   - IP: `192.168.1.50`

Then access via `http://betting.local` or `http://betting`

### Option C: Hosts File (Per Device)

On each device you want to access from:

**Windows:** Edit `C:\Windows\System32\drivers\etc\hosts`
**Mac/Linux:** Edit `/etc/hosts`

Add:
```
192.168.1.50  betting.local
```

Then access via `http://betting.local`

---

## Part 9: Maintenance Commands

### View Application Logs

```bash
sudo journalctl -u betting-syndicate -f
```

### Restart Application

```bash
sudo systemctl restart betting-syndicate
```

### Update Application

```bash
cd /opt/betting-syndicate
source venv/bin/activate
git pull  # If using git
pip install -r requirements.txt
sudo systemctl restart betting-syndicate
```

### Backup Database

```bash
cp /opt/betting-syndicate/betting_syndicate.db ~/backups/betting_syndicate_$(date +%Y%m%d).db
```

### Restore Database

```bash
sudo systemctl stop betting-syndicate
cp ~/backups/betting_syndicate_YYYYMMDD.db /opt/betting-syndicate/betting_syndicate.db
sudo systemctl start betting-syndicate
```

---

## Troubleshooting

### Application Won't Start

Check logs:
```bash
sudo journalctl -u betting-syndicate -n 50
```

### Can't Access from Network

1. Check VM is running: Proxmox web interface
2. Check service is running: `sudo systemctl status betting-syndicate`
3. Check nginx is running: `sudo systemctl status nginx`
4. Check firewall: `sudo ufw status`
5. Ping the VM from your computer: `ping 192.168.1.50`

### Database Errors

Ensure the database file has correct permissions:
```bash
sudo chown admin:admin /opt/betting-syndicate/betting_syndicate.db
chmod 644 /opt/betting-syndicate/betting_syndicate.db
```

### Permission Denied on Uploads

```bash
sudo chown -R admin:admin /opt/betting-syndicate/uploads
chmod -R 755 /opt/betting-syndicate/uploads
```

---

## Quick Reference

| Item | Value |
|------|-------|
| VM IP | `192.168.1.50` (your IP) |
| Web URL | `http://192.168.1.50` |
| SSH | `ssh admin@192.168.1.50` |
| App Directory | `/opt/betting-syndicate` |
| Service Name | `betting-syndicate` |
| Logs | `sudo journalctl -u betting-syndicate -f` |
| Restart | `sudo systemctl restart betting-syndicate` |

---

## Related Documentation

- [DATABASE.md](DATABASE.md) - Database schema and ledger system
- [SEASONS.md](SEASONS.md) - Season management guide
