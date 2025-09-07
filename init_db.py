#!/usr/bin/env python3
"""Initialize database for PackRat deployment"""

import os
import sys
from app import TCGInventoryManager

def init_database():
    """Initialize empty database for deployment"""
    try:
        # Create inventory manager (will initialize database)
        db_path = os.environ.get('DATABASE_PATH', 'inventory.db')
        print(f"Initializing database at: {db_path}")
        
        inventory = TCGInventoryManager(db_path=db_path)
        print("✅ Database initialized successfully!")
        
        # Create a default admin user
        conn = inventory.get_db_connection()
        try:
            from app import hash_password
            admin_email = "admin@packrat.local"
            admin_password = "packrat123"  # Users should change this
            
            conn.execute('''
                INSERT OR IGNORE INTO users (email, password_hash, created_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            ''', (admin_email, hash_password(admin_password)))
            
            conn.commit()
            print(f"✅ Default admin user created: {admin_email}")
            print("   Password: packrat123 (please change after first login)")
            
        except Exception as e:
            print(f"⚠️  Could not create admin user: {e}")
        finally:
            conn.close()
            
        return True
        
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        return False

if __name__ == '__main__':
    success = init_database()
    sys.exit(0 if success else 1)