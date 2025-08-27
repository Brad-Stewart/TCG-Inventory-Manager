from flask import Flask
import os

# Create a simple Flask app for Vercel
app = Flask(__name__)

@app.route('/')
def home():
    return '''
    <html>
    <head><title>PackRat TCG Inventory</title></head>
    <body style="font-family: Arial; text-align: center; padding: 50px;">
        <h1>🃏 PackRat TCG Inventory Manager</h1>
        <p><strong>Deployment Status:</strong> Vercel has limitations with SQLite databases</p>
        <h2>🚀 Recommended Deployment Options:</h2>
        <div style="text-align: left; max-width: 600px; margin: 0 auto;">
            <h3>Option 1: Railway (Best for Production)</h3>
            <ol>
                <li>Go to <a href="https://railway.app" target="_blank">railway.app</a></li>
                <li>Click "New Project" → "Deploy from GitHub"</li>  
                <li>Select your TCG-Inventory-Manager repository</li>
                <li>Railway will auto-deploy with persistent SQLite database!</li>
            </ol>
            
            <h3>Option 2: Local Development</h3>
            <ol>
                <li>Clone the repository locally</li>
                <li>Run: <code>pip install -r requirements.txt</code></li>
                <li>Run: <code>python app.py</code></li>
                <li>Access at: <code>http://localhost:5001</code></li>
            </ol>
        </div>
        <hr style="margin: 30px 0;">
        <p><small>PackRat is a full-featured TCG inventory management system with Scryfall integration, 
        real-time pricing, advanced filtering, and WUBRG color ordering.</small></p>
    </body>
    </html>
    '''

@app.route('/health')
def health():
    return {'status': 'ok', 'message': 'PackRat deployment helper is running'}

# For Vercel compatibility
if __name__ == '__main__':
    app.run(debug=False)