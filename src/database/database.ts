import sqlite3 from 'sqlite3';
import { promisify } from 'util';
import { Card, User, PriceAlert, CollectionTemplate, CardTemplate, UserCollectionInstance } from '../types';
import path from 'path';

export class Database {
  private db: sqlite3.Database;

  constructor(dbPath?: string) {
    const defaultPath = path.join(process.cwd(), 'inventory.db');
    this.db = new sqlite3.Database(dbPath || process.env.DATABASE_PATH || defaultPath);
    this.db.run('PRAGMA foreign_keys = ON');
    
    
    this.initDatabase();
  }

  private initDatabase(): void {
    const sql = `
      CREATE TABLE IF NOT EXISTS cards (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        card_name TEXT NOT NULL,
        set_name TEXT,
        set_code TEXT,
        collector_number TEXT,
        quantity INTEGER DEFAULT 1,
        is_foil BOOLEAN DEFAULT 0,
        condition TEXT DEFAULT 'Near Mint',
        language TEXT DEFAULT 'English',
        purchase_price REAL DEFAULT 0,
        current_price REAL DEFAULT 0,
        price_change REAL DEFAULT 0,
        total_value REAL DEFAULT 0,
        market_url TEXT,
        image_url TEXT,
        image_url_back TEXT,
        rarity TEXT,
        colors TEXT,
        mana_cost TEXT,
        mana_value INTEGER DEFAULT 0,
        card_type TEXT,
        price_alert_threshold REAL DEFAULT 0,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        user_id INTEGER NOT NULL,
        template_hash TEXT,
        source_template_id INTEGER,
        FOREIGN KEY (user_id) REFERENCES users (id)
      );

      CREATE TABLE IF NOT EXISTS price_alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        card_id INTEGER NOT NULL,
        alert_type TEXT NOT NULL,
        threshold_value REAL NOT NULL,
        current_value REAL NOT NULL,
        triggered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_read BOOLEAN DEFAULT 0,
        FOREIGN KEY (card_id) REFERENCES cards (id)
      );

      CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_login TIMESTAMP
      );

      CREATE TABLE IF NOT EXISTS collection_templates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        template_hash TEXT UNIQUE NOT NULL,
        created_by INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_public BOOLEAN DEFAULT 0,
        FOREIGN KEY (created_by) REFERENCES users (id)
      );

      CREATE TABLE IF NOT EXISTS card_templates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        template_id INTEGER NOT NULL,
        card_name TEXT NOT NULL,
        set_name TEXT,
        set_code TEXT,
        collector_number TEXT,
        is_foil BOOLEAN DEFAULT 0,
        condition TEXT DEFAULT 'Near Mint',
        language TEXT DEFAULT 'English',
        quantity INTEGER DEFAULT 1,
        rarity TEXT,
        colors TEXT,
        mana_cost TEXT,
        mana_value INTEGER DEFAULT 0,
        card_type TEXT,
        template_hash TEXT NOT NULL,
        FOREIGN KEY (template_id) REFERENCES collection_templates (id)
      );

      CREATE TABLE IF NOT EXISTS user_collection_instances (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        template_id INTEGER NOT NULL,
        instance_name TEXT NOT NULL,
        imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id),
        FOREIGN KEY (template_id) REFERENCES collection_templates (id),
        UNIQUE(user_id, template_id)
      );
    `;

    this.db.exec(sql);
  }

  // Database query methods
  private async runQuery(sql: string, params: any[] = []): Promise<any> {
    return new Promise((resolve, reject) => {
      this.db.run(sql, params, function(this: any, err: any) {
        if (err) reject(err);
        else resolve({ lastID: this.lastID, changes: this.changes });
      });
    });
  }

  private async getQuery(sql: string, params: any[] = []): Promise<any> {
    return new Promise((resolve, reject) => {
      this.db.get(sql, params, (err: any, row: any) => {
        if (err) reject(err);
        else resolve(row);
      });
    });
  }

  private async allQuery(sql: string, params: any[] = []): Promise<any[]> {
    return new Promise((resolve, reject) => {
      this.db.all(sql, params, (err: any, rows: any[]) => {
        if (err) reject(err);
        else resolve(rows || []);
      });
    });
  }

  // Card operations
  async getCards(userId: number, filters?: any): Promise<Card[]> {
    let sql = 'SELECT * FROM cards WHERE user_id = ?';
    const params: any[] = [userId];

    if (filters?.search) {
      sql += ' AND (LOWER(card_name) LIKE LOWER(?) OR LOWER(set_name) LIKE LOWER(?) OR LOWER(card_type) LIKE LOWER(?))';
      const searchParam = `%${filters.search}%`;
      params.push(searchParam, searchParam, searchParam);
    }

    if (filters?.rarity) {
      sql += ' AND rarity = ?';
      params.push(filters.rarity);
    }

    if (filters?.color) {
      sql += ' AND colors LIKE ?';
      params.push(`%${filters.color}%`);
    }

    if (filters?.card_type) {
      sql += ' AND card_type LIKE ?';
      params.push(`%${filters.card_type}%`);
    }

    if (filters?.mana_min !== undefined) {
      sql += ' AND mana_value >= ?';
      params.push(parseInt(filters.mana_min));
    }

    if (filters?.mana_max !== undefined) {
      sql += ' AND mana_value <= ?';
      params.push(parseInt(filters.mana_max));
    }

    const validSorts = ['card_name', 'set_name', 'current_price', 'total_value', 'quantity', 'mana_value'];
    const sortBy = validSorts.includes(filters?.sort) ? filters.sort : 'total_value';
    const order = filters?.order === 'asc' ? 'ASC' : 'DESC';
    
    sql += ` ORDER BY ${sortBy} ${order}`;

    if (filters?.limit) {
      sql += ' LIMIT ?';
      params.push(filters.limit);
    }

    if (filters?.offset) {
      sql += ' OFFSET ?';
      params.push(filters.offset);
    }

    return await this.allQuery(sql, params) as Card[];
  }

  async getCardById(cardId: number, userId: number): Promise<Card | null> {
    const result = await this.getQuery('SELECT * FROM cards WHERE id = ? AND user_id = ?', [cardId, userId]);
    return result as Card | null;
  }

  async addCard(card: Omit<Card, 'id'>): Promise<number> {
    const sql = `
      INSERT INTO cards (
        card_name, set_name, set_code, collector_number, quantity, 
        is_foil, condition, language, purchase_price, current_price, 
        price_change, total_value, market_url, image_url, image_url_back,
        rarity, colors, mana_cost, mana_value, card_type,
        price_alert_threshold, user_id, last_updated
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `;

    const result = await this.runQuery(sql, [
      card.card_name, card.set_name, card.set_code, card.collector_number,
      card.quantity, card.is_foil, card.condition, card.language,
      card.purchase_price, card.current_price, card.price_change,
      card.total_value, card.market_url, card.image_url, card.image_url_back,
      card.rarity, card.colors, card.mana_cost, card.mana_value,
      card.card_type, card.price_alert_threshold, card.user_id, card.last_updated
    ]);

    return result.lastID;
  }

  async updateCard(cardId: number, card: Partial<Card>): Promise<void> {
    const fields = Object.keys(card).map(key => `${key} = ?`).join(', ');
    const values = Object.values(card);
    values.push(cardId);

    await this.runQuery(`UPDATE cards SET ${fields} WHERE id = ?`, values);
  }

  async deleteCard(cardId: number, userId: number): Promise<void> {
    await this.runQuery('DELETE FROM cards WHERE id = ? AND user_id = ?', [cardId, userId]);
  }

  async getCardCount(userId: number, filters?: any): Promise<number> {
    let sql = 'SELECT COUNT(*) as count FROM cards WHERE user_id = ?';
    const params: any[] = [userId];

    // Apply same filters as getCards
    if (filters?.search) {
      sql += ' AND (LOWER(card_name) LIKE LOWER(?) OR LOWER(set_name) LIKE LOWER(?) OR LOWER(card_type) LIKE LOWER(?))';
      const searchParam = `%${filters.search}%`;
      params.push(searchParam, searchParam, searchParam);
    }

    const result = await this.getQuery(sql, params) as { count: number };
    return result.count;
  }

  async getCollectionStats(userId: number): Promise<any> {
    const result = await this.getQuery(`
      SELECT 
        COUNT(*) as total_cards,
        SUM(quantity) as total_quantity, 
        SUM(total_value) as total_value,
        AVG(current_price) as avg_price
      FROM cards WHERE user_id = ?
    `, [userId]);

    return result;
  }

  // User operations
  async getUserByEmail(email: string): Promise<User | null> {
    const result = await this.getQuery('SELECT * FROM users WHERE email = ?', [email]);
    return result as User | null;
  }

  async getUserById(id: number): Promise<User | null> {
    const result = await this.getQuery('SELECT * FROM users WHERE id = ?', [id]);
    return result as User | null;
  }

  async createUser(user: Omit<User, 'id'>): Promise<number> {
    const result = await this.runQuery(
      'INSERT INTO users (email, password_hash, created_at) VALUES (?, ?, ?)',
      [user.email, user.password_hash, user.created_at]
    );
    return result.lastID;
  }

  async updateUserLastLogin(userId: number): Promise<void> {
    await this.runQuery(
      'UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?',
      [userId]
    );
  }

  // Filter options
  async getFilterOptions(userId: number): Promise<any> {
    const rarities = await this.allQuery(
      'SELECT DISTINCT rarity FROM cards WHERE user_id = ? AND rarity IS NOT NULL AND rarity != "" ORDER BY rarity',
      [userId]
    );

    const colors = await this.allQuery(
      'SELECT DISTINCT colors FROM cards WHERE user_id = ? AND colors IS NOT NULL AND colors != "" ORDER BY colors',
      [userId]
    );

    const cardTypes = await this.allQuery(
      'SELECT DISTINCT card_type FROM cards WHERE user_id = ? AND card_type IS NOT NULL AND card_type != "" ORDER BY card_type',
      [userId]
    );

    return { rarities, colors, cardTypes };
  }

  close(): void {
    this.db.close();
  }
}