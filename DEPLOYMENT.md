# 🚀 PackRat Deployment Guide

## ⚠️ Vercel Issue
Vercel doesn't support SQLite databases in production due to serverless limitations. Use Railway instead!

## ✅ Recommended: Railway Deployment

### Step 1: Deploy to Railway
1. Go to **[railway.app](https://railway.app)**
2. Click **"Start a New Project"**
3. Select **"Deploy from GitHub repo"**
4. Choose your `TCG-Inventory-Manager` repository
5. Railway will automatically detect the configuration and deploy!

### Step 2: Set Environment Variables (Optional)
In Railway dashboard:
- `SECRET_KEY`: Set a secure random string
- `DATABASE_PATH`: Leave default (inventory.db)

### Step 3: Access Your App
- Railway will provide a URL like `https://your-app.up.railway.app`
- Login with: `admin@packrat.local` / `packrat123`
- **Change the password immediately!**

## 🎯 Alternative: Local Network Deployment

### Run on Local Network:
```bash
python app.py
```
Access at: `http://your-ip:5001`

## 🔧 Production Tips
- Change default admin password immediately
- Import your card collection via CSV
- Set up proper backup strategy for SQLite database

---
**PackRat is ready to manage your TCG collection! 🃏**