import { Router, Request, Response } from 'express';
import { Database } from '../database/database';
import { AuthService } from '../services/auth';

export function createAuthRoutes(db: Database): Router {
  const router = Router();

  // Login page
  router.get('/login', (req: Request, res: Response) => {
    res.render('login');
  });

  // Login POST
  router.post('/login', async (req: Request, res: Response) => {
    try {
      const { email, password } = req.body;

      if (!email || !password) {
        req.flash('error', 'Email and password are required');
        res.redirect('/login');
        return;
      }

      const user = await AuthService.authenticateUser(db, email, password);

      if (user && user.id) {
        req.session.user_id = user.id;
        req.session.user_email = user.email;
        res.redirect('/');
        return;
      } else {
        req.flash('error', 'Invalid email or password');
        res.redirect('/login');
        return;
      }
    } catch (error) {
      console.error('Login error:', error);
      req.flash('error', 'An error occurred during login');
      res.redirect('/login');
    }
  });

  // Register page
  router.get('/register', (req: Request, res: Response) => {
    res.render('register');
  });

  // Register POST
  router.post('/register', async (req: Request, res: Response) => {
    try {
      const { email, password, confirm_password } = req.body;

      if (!email || !password || !confirm_password) {
        req.flash('error', 'All fields are required');
        res.redirect('/register');
        return;
      }

      if (password !== confirm_password) {
        req.flash('error', 'Passwords do not match');
        res.redirect('/register');
        return;
      }

      await AuthService.registerUser(db, email, password);
      req.flash('success', 'Registration successful! Please log in.');
      res.redirect('/login');

    } catch (error: any) {
      console.error('Registration error:', error);
      if (error.message === 'Email already exists') {
        req.flash('error', 'Email already exists');
      } else {
        req.flash('error', 'An error occurred during registration');
      }
      res.redirect('/register');
    }
  });

  // Logout
  router.get('/logout', (req: Request, res: Response) => {
    req.session.destroy((err) => {
      if (err) {
        console.error('Logout error:', err);
      }
      res.redirect('/login');
    });
  });

  return router;
}