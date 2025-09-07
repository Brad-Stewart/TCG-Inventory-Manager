import axios from 'axios';
import { ScryfallCard } from '../types';

export class ScryfallService {
  private static readonly BASE_URL = 'https://api.scryfall.com';
  private static readonly RATE_LIMIT_DELAY = 100; // 100ms between requests

  private static async delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  static async searchCard(cardName: string, setCode?: string, collectorNumber?: string): Promise<ScryfallCard | null> {
    try {
      // Build search query
      let query = `!"${cardName}"`;
      if (setCode) {
        query += ` set:${setCode}`;
      }
      if (collectorNumber) {
        query += ` cn:${collectorNumber}`;
      }

      const url = `${this.BASE_URL}/cards/search?q=${encodeURIComponent(query)}`;
      const response = await axios.get(url, { timeout: 10000 });

      // Rate limiting respect
      await this.delay(this.RATE_LIMIT_DELAY);

      if (response.status === 200 && response.data.total_cards > 0) {
        const cardData = response.data.data[0];
        return this.extractCardData(cardData);
      }

      // Fallback: try fuzzy search without set/collector number
      if (setCode || collectorNumber) {
        const fallbackQuery = `!"${cardName}"`;
        const fallbackUrl = `${this.BASE_URL}/cards/search?q=${encodeURIComponent(fallbackQuery)}`;
        const fallbackResponse = await axios.get(fallbackUrl, { timeout: 10000 });

        await this.delay(this.RATE_LIMIT_DELAY);

        if (fallbackResponse.status === 200 && fallbackResponse.data.total_cards > 0) {
          const cardData = fallbackResponse.data.data[0];
          return this.extractCardData(cardData);
        }
      }

      return null;
    } catch (error) {
      console.error(`Scryfall API error for ${cardName}:`, error);
      return null;
    }
  }

  static async searchCardsFuzzy(query: string): Promise<ScryfallCard[]> {
    try {
      if (query.length < 2) {
        return [];
      }

      const searchUrl = `${this.BASE_URL}/cards/search`;
      const params = {
        q: `!"${query}" OR "${query}"`, // Exact match first, then fuzzy
        order: 'name',
        unique: 'prints'
      };

      const response = await axios.get(searchUrl, { params, timeout: 5000 });
      await this.delay(50); // Shorter delay for searches

      if (response.status === 200) {
        const cards = response.data.data || [];
        
        // Sort by relevance using simple string matching
        const sortedCards = cards.sort((a: any, b: any) => {
          const aName = a.name.toLowerCase();
          const bName = b.name.toLowerCase();
          const queryLower = query.toLowerCase();
          
          const aExact = aName === queryLower ? 1 : 0;
          const bExact = bName === queryLower ? 1 : 0;
          if (aExact !== bExact) return bExact - aExact;
          
          const aStarts = aName.startsWith(queryLower) ? 1 : 0;
          const bStarts = bName.startsWith(queryLower) ? 1 : 0;
          if (aStarts !== bStarts) return bStarts - aStarts;
          
          const aContains = aName.includes(queryLower) ? 1 : 0;
          const bContains = bName.includes(queryLower) ? 1 : 0;
          return bContains - aContains;
        });

        return sortedCards.slice(0, 10).map((card: any) => this.extractCardData(card));
      }

      return [];
    } catch (error) {
      console.error('Card search error:', error);
      return [];
    }
  }

  private static extractCardData(data: any): ScryfallCard {
    // Handle image URLs - double-faced cards have different structure
    let imageUrl = '';
    let imageUrlBack = '';

    if (data.image_uris) {
      // Single-faced card
      imageUrl = data.image_uris.normal || '';
    } else if (data.card_faces && data.card_faces.length > 0) {
      // Double-faced card - get both faces
      const firstFace = data.card_faces[0];
      if (firstFace.image_uris) {
        imageUrl = firstFace.image_uris.normal || '';
      }

      // Get second face if it exists
      if (data.card_faces.length > 1) {
        const secondFace = data.card_faces[1];
        if (secondFace.image_uris) {
          imageUrlBack = secondFace.image_uris.normal || '';
        }
      }
    }

    // Get mana cost and calculate mana value properly
    let manaCost = data.mana_cost || '';
    if (!manaCost && data.card_faces && data.card_faces.length > 0) {
      const firstFace = data.card_faces[0];
      manaCost = firstFace.mana_cost || '';
    }

    // Calculate mana value from mana cost
    const manaValue = this.calculateManaValue(manaCost);

    // Clean up mana cost display (remove brackets)
    const manaCostDisplay = this.formatManaCostForDisplay(manaCost);

    // Format colors in WUBRG order without commas
    const colorsFormatted = this.formatColorsWubrg(data.colors || []);

    // Handle double-faced cards for type
    let cardType = data.type_line || '';
    if (!cardType && data.card_faces && data.card_faces.length > 0) {
      const firstFace = data.card_faces[0];
      cardType = firstFace.type_line || '';
    }

    return {
      name: data.name || '',
      set_name: data.set_name || '',
      set: (data.set || '').toUpperCase(),
      collector_number: data.collector_number || '',
      mana_cost: manaCostDisplay,
      mana_value: manaValue,
      type_line: cardType,
      rarity: (data.rarity || '').replace(/^\w/, (c: string) => c.toUpperCase()), // Title case
      colors: data.colors || [],
      prices: {
        usd: data.prices?.usd,
        usd_foil: data.prices?.usd_foil
      },
      image_uris: {
        normal: imageUrl,
        small: data.image_uris?.small || (data.card_faces?.[0]?.image_uris?.small || '')
      },
      card_faces: data.card_faces,
      scryfall_uri: data.scryfall_uri || ''
    };
  }

  private static calculateManaValue(manaCost: string): number {
    if (!manaCost || manaCost.trim() === '') {
      return 0;
    }

    // Remove any spaces and convert to upper case
    manaCost = manaCost.trim().toUpperCase();

    // Find all mana symbols within curly braces
    const manaSymbols = manaCost.match(/\{([^}]+)\}/g) || [];
    
    let totalCmc = 0;

    for (const symbol of manaSymbols) {
      const content = symbol.slice(1, -1); // Remove curly braces

      // Handle hybrid mana like {2/W} or {W/U}
      if (content.includes('/')) {
        // For hybrid mana, take the higher cost (or 1 if both are colors)
        const parts = content.split('/');
        const costs = parts.map(part => {
          if (/^\d+$/.test(part)) {
            return parseInt(part);
          } else if (['W', 'U', 'B', 'R', 'G', 'C'].includes(part)) {
            return 1;
          } else if (part === 'P') { // Phyrexian
            return 1;
          }
          return 1;
        });
        totalCmc += Math.max(...costs);
      }
      // Handle regular numeric costs
      else if (/^\d+$/.test(content)) {
        totalCmc += parseInt(content);
      }
      // Handle X, Y, Z (variable costs - count as 0 for CMC)
      else if (['X', 'Y', 'Z'].includes(content)) {
        totalCmc += 0; // X costs don't count toward CMC
      }
      // Handle regular color symbols
      else if (['W', 'U', 'B', 'R', 'G', 'C', 'S'].includes(content)) {
        totalCmc += 1;
      }
    }

    return totalCmc;
  }

  private static formatManaCostForDisplay(manaCost: string): string {
    if (!manaCost || manaCost.trim() === '') {
      return '';
    }

    // Remove all curly braces
    return manaCost.replace(/[{}]/g, '');
  }

  private static formatColorsWubrg(colorsList: string[]): string {
    if (!colorsList || colorsList.length === 0) {
      return '';
    }

    // WUBRG order
    const wubrgOrder = ['W', 'U', 'B', 'R', 'G'];
    
    // Filter and sort colors according to WUBRG order
    const orderedColors = wubrgOrder.filter(color => colorsList.includes(color));
    
    return orderedColors.join('');
  }
}