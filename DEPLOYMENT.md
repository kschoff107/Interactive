# Deployment Guide for Render

This guide will help you deploy the Code Visualizer application to Render.

## Prerequisites

- A GitHub account with your code pushed to a repository
- A Render account (free tier available at https://render.com)

## Deployment Steps

### Option 1: Deploy with Blueprint (Recommended)

1. **Push all changes to GitHub** (we'll do this together)

2. **Go to Render Dashboard**
   - Visit https://dashboard.render.com
   - Click "New +" button
   - Select "Blueprint"

3. **Connect your GitHub repository**
   - Select "Interactive" repository
   - Render will automatically detect the `render.yaml` file

4. **Update the Frontend Environment Variable**
   - After the backend service is created, copy its URL (e.g., `https://code-visualizer-api.onrender.com`)
   - Go to the frontend service settings
   - Update `REACT_APP_API_URL` to: `https://YOUR-BACKEND-URL.onrender.com/api`
   - Click "Save Changes"

5. **Wait for deployment**
   - Backend will deploy first (3-5 minutes)
   - Frontend will deploy after (2-3 minutes)
   - Database will be created automatically

6. **Access your application**
   - Your frontend URL will be: `https://code-visualizer-frontend.onrender.com`
   - You can customize this URL in Render settings

## Auto-Deploy on Push

Once set up, Render will automatically:
- Detect when you push to GitHub
- Rebuild and redeploy your application
- Usually takes 3-5 minutes for changes to go live

## Important Notes

1. **Free Tier Limitations:**
   - Services spin down after 15 minutes of inactivity
   - First request after spin-down takes 30-60 seconds

2. **Making Changes:**
   - Continue developing locally as usual
   - Test on localhost:3000
   - Commit and push to GitHub
   - Render automatically redeploys

---

Ready to deploy? Let's push these changes to GitHub first!
