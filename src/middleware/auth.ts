import { Request, Response, NextFunction } from 'express';

declare global {
  namespace Express {
    interface Request {
      user?: {
        id: number;
        email: string;
      };
    }
  }
}

export function requireAuth(req: Request, res: Response, next: NextFunction): void {
  if (!req.session?.user_id) {
    res.redirect('/login');
    return;
  }

  // Add user info to request
  req.user = {
    id: req.session.user_id,
    email: req.session.user_email || ''
  };

  next();
}

export function getCurrentUserId(req: Request): number | null {
  return req.session?.user_id || null;
}