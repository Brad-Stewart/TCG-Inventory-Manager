import bcrypt from 'bcrypt';
import { Database } from '../database/database';
import { User } from '../types';

export class AuthService {
  private static readonly SALT_ROUNDS = 10;

  static async hashPassword(password: string): Promise<string> {
    return await bcrypt.hash(password, this.SALT_ROUNDS);
  }

  static async verifyPassword(password: string, hash: string): Promise<boolean> {
    return await bcrypt.compare(password, hash);
  }

  static async authenticateUser(db: Database, email: string, password: string): Promise<User | null> {
    try {
      const user = await db.getUserByEmail(email);
      if (!user) {
        return null;
      }

      const isValidPassword = await this.verifyPassword(password, user.password_hash);
      if (!isValidPassword) {
        return null;
      }

      // Update last login
      if (user.id) {
        await db.updateUserLastLogin(user.id);
      }

      return user;
    } catch (error) {
      console.error('Authentication error:', error);
      return null;
    }
  }

  static async registerUser(db: Database, email: string, password: string): Promise<User | null> {
    try {
      // Check if user already exists
      const existingUser = await db.getUserByEmail(email);
      if (existingUser) {
        throw new Error('Email already exists');
      }

      // Hash password and create user
      const passwordHash = await this.hashPassword(password);
      const userId = await db.createUser({
        email,
        password_hash: passwordHash,
        created_at: new Date().toISOString()
      });

      return await db.getUserById(userId);
    } catch (error) {
      console.error('Registration error:', error);
      throw error;
    }
  }

  static async createDefaultAdmin(db: Database): Promise<void> {
    try {
      const adminEmail = 'admin@packrat.local';
      const adminPassword = 'packrat123';

      // Check if admin user already exists
      const existingAdmin = await db.getUserByEmail(adminEmail);
      
      if (!existingAdmin) {
        const passwordHash = await this.hashPassword(adminPassword);
        await db.createUser({
          email: adminEmail,
          password_hash: passwordHash,
          created_at: new Date().toISOString()
        });
        console.log('✅ Default admin user created: admin@packrat.local / packrat123');
      } else {
        console.log('ℹ️ Admin user already exists');
      }
    } catch (error) {
      console.error('❌ Could not create admin user:', error);
    }
  }
}