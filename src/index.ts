import express from 'express';
import session from 'express-session';
import bodyParser from 'body-parser';
import path from 'path';
import { Database } from './database/database';
import { AuthService } from './services/auth';
import { createAuthRoutes } from './routes/auth';
import { createCardRoutes } from './routes/cards';
import { createApiRoutes } from './routes/api';

// Initialize app
const app = express();
const port = parseInt(process.env.PORT || '5001');

// Initialize database
const db = new Database();

// Configure Express
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, '../views'));

// Middleware
app.use(bodyParser.urlencoded({ extended: true }));
app.use(bodyParser.json());
app.use(express.static(path.join(__dirname, '../public')));

// Session configuration
app.use(session({
  secret: process.env.SECRET_KEY || 'your-secret-key-here',
  resave: false,
  saveUninitialized: false,
  cookie: {
    secure: process.env.NODE_ENV === 'production',
    maxAge: 24 * 60 * 60 * 1000 // 24 hours
  }
}));

// Flash messages middleware
app.use((req, res, next) => {
  res.locals.flash = req.session.flash || {};
  req.session.flash = {};
  
  req.flash = (type: string, message: string) => {
    if (!req.session.flash) {
      req.session.flash = {};
    }
    if (!req.session.flash[type]) {
      req.session.flash[type] = [];
    }
    req.session.flash[type].push(message);
  };
  
  next();
});

// Make session available in templates
app.use((req, res, next) => {
  res.locals.session = req.session;
  next();
});

// Routes
app.use('/', createAuthRoutes(db));
app.use('/', createCardRoutes(db));
app.use('/api', createApiRoutes(db));

// Error handling
app.use((error: Error, req: express.Request, res: express.Response, next: express.NextFunction) => {
  console.error('Error:', error);
  res.status(500).render('error', { error: 'Internal Server Error' });
});

// 404 handling
app.use((req, res) => {
  res.status(404).render('error', { error: 'Page Not Found' });
});

// Initialize default admin user
AuthService.createDefaultAdmin(db).then(() => {
  // Start server
  app.listen(port, '0.0.0.0', () => {
    console.log(`🚀 TCG Inventory Server running at http://localhost:${port}`);
    console.log(`📊 Default admin: admin@packrat.local / packrat123`);
  });
});

// Graceful shutdown
process.on('SIGTERM', () => {
  console.log('SIGTERM received, shutting down gracefully');
  db.close();
  process.exit(0);
});

process.on('SIGINT', () => {
  console.log('SIGINT received, shutting down gracefully');
  db.close();
  process.exit(0);
});