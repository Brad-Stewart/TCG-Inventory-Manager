export interface Card {
  id?: number;
  card_name: string;
  set_name?: string;
  set_code?: string;
  collector_number?: string;
  quantity: number;
  is_foil: boolean;
  condition: string;
  language: string;
  purchase_price: number;
  current_price: number;
  price_change: number;
  total_value: number;
  market_url?: string;
  image_url?: string;
  image_url_back?: string;
  rarity?: string;
  colors?: string;
  mana_cost?: string;
  mana_value: number;
  card_type?: string;
  price_alert_threshold: number;
  last_updated: string;
  user_id: number;
  template_hash?: string;
  source_template_id?: number;
}

export interface User {
  id?: number;
  email: string;
  password_hash: string;
  created_at: string;
  last_login?: string;
}

export interface PriceAlert {
  id?: number;
  card_id: number;
  alert_type: string;
  threshold_value: number;
  current_value: number;
  triggered_at: string;
  is_read: boolean;
}

export interface CollectionTemplate {
  id?: number;
  name: string;
  description?: string;
  template_hash: string;
  created_by: number;
  created_at: string;
  is_public: boolean;
}

export interface CardTemplate {
  id?: number;
  template_id: number;
  card_name: string;
  set_name?: string;
  set_code?: string;
  collector_number?: string;
  is_foil: boolean;
  condition: string;
  language: string;
  quantity: number;
  rarity?: string;
  colors?: string;
  mana_cost?: string;
  mana_value: number;
  card_type?: string;
  template_hash: string;
}

export interface UserCollectionInstance {
  id?: number;
  user_id: number;
  template_id: number;
  instance_name: string;
  imported_at: string;
}

export interface ScryfallCard {
  name: string;
  set_name: string;
  set: string;
  collector_number: string;
  mana_cost: string;
  mana_value?: number;
  type_line: string;
  rarity: string;
  colors: string[];
  prices: {
    usd?: string;
    usd_foil?: string;
  };
  image_uris?: {
    normal?: string;
    small?: string;
  };
  card_faces?: Array<{
    name: string;
    mana_cost: string;
    type_line: string;
    image_uris?: {
      normal?: string;
      small?: string;
    };
  }>;
  scryfall_uri: string;
}

export interface ProgressState {
  type: 'start' | 'progress' | 'complete' | 'error';
  message: string;
  current?: number;
  total?: number;
  phase?: string;
  imported_count?: number;
  updated_count?: number;
  error?: string;
}

export interface FilterParams {
  search?: string;
  rarity?: string;
  color?: string;
  card_type?: string;
  mana_min?: string;
  mana_max?: string;
  sort?: string;
  order?: string;
  page?: number;
}

declare module 'express-session' {
  interface SessionData {
    user_id?: number;
    user_email?: string;
    flash?: {
      [key: string]: string[];
    };
  }
}

declare global {
  namespace Express {
    interface Request {
      flash: (type: string, message: string) => void;
    }
  }
}