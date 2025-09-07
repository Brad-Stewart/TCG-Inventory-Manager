import fs from 'fs';
import csv from 'csv-parser';
import { Card, ProgressState } from '../types';
import { Database } from '../database/database';
import { ScryfallService } from './scryfall';
import { createHash } from 'crypto';

export interface CSVRow {
  [key: string]: string;
}

export class CSVImportService {
  private static readonly BATCH_SIZE = 100;
  private static progressState: { [userId: number]: ProgressState } = {};
  private static activeUpdates: { [userId: number]: boolean } = {};

  static getProgressState(userId: number): ProgressState | null {
    return this.progressState[userId] || null;
  }

  static isUpdateActive(userId: number): boolean {
    return this.activeUpdates[userId] || false;
  }

  static async importCSV(
    filePath: string,
    userId: number,
    db: Database,
    onProgress?: (progress: ProgressState) => void
  ): Promise<{ importedCount: number; updatedCount: number }> {
    return new Promise((resolve, reject) => {
      const cards: CSVRow[] = [];

      // Initialize progress
      this.progressState[userId] = {
        type: 'start',
        message: 'Reading CSV file...',
        current: 0,
        total: 0,
        phase: 'reading'
      };
      this.activeUpdates[userId] = true;

      if (onProgress) onProgress(this.progressState[userId]);

      fs.createReadStream(filePath)
        .pipe(csv())
        .on('data', (row) => {
          cards.push(row);
        })
        .on('end', async () => {
          try {
            this.progressState[userId] = {
              type: 'progress',
              message: `Processing ${cards.length} cards...`,
              current: 0,
              total: cards.length,
              phase: 'processing'
            };

            if (onProgress) onProgress(this.progressState[userId]);

            const processedCards = await this.preprocessCSVData(cards, userId);
            const { importedCount, importedCardIds } = await this.importCardsWithProgress(
              processedCards,
              userId,
              db,
              onProgress
            );

            let updatedCount = 0;
            if (importedCardIds.length > 0) {
              updatedCount = await this.updateCardPricesAndMetadataWithProgress(
                importedCardIds,
                userId,
                db,
                onProgress
              );
            }

            this.progressState[userId] = {
              type: 'complete',
              message: `Successfully imported ${importedCount} cards with ${updatedCount} price updates.`,
              imported_count: importedCount,
              updated_count: updatedCount,
              total: cards.length
            };

            if (onProgress) onProgress(this.progressState[userId]);

            this.activeUpdates[userId] = false;
            resolve({ importedCount, updatedCount });

          } catch (error) {
            this.progressState[userId] = {
              type: 'error',
              message: `Import failed: ${error}`,
              error: String(error)
            };

            if (onProgress) onProgress(this.progressState[userId]);

            this.activeUpdates[userId] = false;
            reject(error);
          }
        })
        .on('error', (error) => {
          this.progressState[userId] = {
            type: 'error',
            message: `Error reading CSV: ${error}`,
            error: String(error)
          };

          if (onProgress) onProgress(this.progressState[userId]);

          this.activeUpdates[userId] = false;
          reject(error);
        });
    });
  }

  private static async preprocessCSVData(rows: CSVRow[], userId: number): Promise<Partial<Card>[]> {
    return rows.map((row) => {
      // Map common CSV column variations to our card structure
      const card: Partial<Card> = {
        card_name: this.getColumnValue(row, ['card_name', 'Card Name', 'name', 'Name']),
        set_name: this.getColumnValue(row, ['set_name', 'Set Name', 'set', 'Set']),
        set_code: this.getColumnValue(row, ['set_code', 'Set Code', 'setCode']),
        collector_number: this.getColumnValue(row, ['collector_number', 'Collector Number', 'collectorNumber', 'number']),
        quantity: parseInt(this.getColumnValue(row, ['quantity', 'Quantity', 'qty', 'Qty']) || '1'),
        is_foil: this.parseBoolean(this.getColumnValue(row, ['is_foil', 'Is Foil', 'foil', 'Foil'])),
        condition: this.getColumnValue(row, ['condition', 'Condition']) || 'Near Mint',
        language: this.getColumnValue(row, ['language', 'Language']) || 'English',
        purchase_price: parseFloat(this.getColumnValue(row, ['purchase_price', 'Purchase Price', 'purchasePrice']) || '0'),
        current_price: 0,
        price_change: 0,
        total_value: 0,
        rarity: this.getColumnValue(row, ['rarity', 'Rarity']),
        colors: this.getColumnValue(row, ['colors', 'Colors']),
        mana_cost: this.getColumnValue(row, ['mana_cost', 'Mana Cost', 'manaCost']),
        mana_value: parseInt(this.getColumnValue(row, ['mana_value', 'Mana Value', 'manaValue', 'cmc', 'CMC']) || '0'),
        card_type: this.getColumnValue(row, ['card_type', 'Card Type', 'cardType', 'type', 'Type']),
        price_alert_threshold: 0,
        last_updated: new Date().toISOString(),
        user_id: userId
      };

      return card;
    });
  }

  private static getColumnValue(row: CSVRow, possibleKeys: string[]): string {
    for (const key of possibleKeys) {
      if (row[key] !== undefined && row[key] !== null && row[key] !== '') {
        return row[key].trim();
      }
    }
    return '';
  }

  private static parseBoolean(value: string): boolean {
    if (!value) return false;
    const lower = value.toLowerCase().trim();
    return lower === 'true' || lower === '1' || lower === 'yes' || lower === 'y';
  }

  private static async importCardsWithProgress(
    cards: Partial<Card>[],
    userId: number,
    db: Database,
    onProgress?: (progress: ProgressState) => void
  ): Promise<{ importedCount: number; importedCardIds: number[] }> {
    let importedCount = 0;
    const importedCardIds: number[] = [];

    for (let i = 0; i < cards.length; i++) {
      const card = cards[i];
      
      // Update progress
      this.progressState[userId] = {
        type: 'progress',
        message: `Importing card ${i + 1} of ${cards.length}: ${card.card_name}`,
        current: i + 1,
        total: cards.length,
        phase: 'importing'
      };

      if (onProgress) onProgress(this.progressState[userId]);

      try {
        // Check if card already exists for this user
        const existingCards = await db.getCards(userId, {
          search: card.card_name,
          limit: 1
        });

        const existingCard = existingCards.find(c => 
          c.card_name === card.card_name &&
          c.set_code === card.set_code &&
          c.collector_number === card.collector_number &&
          c.is_foil === card.is_foil &&
          c.condition === card.condition
        );

        if (existingCard && existingCard.id) {
          // Update quantity instead of creating duplicate
          const newQuantity = existingCard.quantity + (card.quantity || 1);
          await db.updateCard(existingCard.id, {
            quantity: newQuantity,
            last_updated: new Date().toISOString()
          });
          importedCardIds.push(existingCard.id);
        } else {
          // Insert new card
          const cardData = {
            ...card,
            current_price: 0,
            price_change: 0,
            total_value: 0
          } as Omit<Card, 'id'>;

          const cardId = await db.addCard(cardData);
          importedCardIds.push(cardId);
        }

        importedCount++;

      } catch (error) {
        console.error(`Error importing card ${card.card_name}:`, error);
      }

      // Small delay to prevent overwhelming the system
      if (i % 10 === 0) {
        await new Promise(resolve => setTimeout(resolve, 10));
      }
    }

    return { importedCount, importedCardIds };
  }

  static async updateCardPricesAndMetadataWithProgress(
    cardIds: number[],
    userId: number,
    db: Database,
    onProgress?: (progress: ProgressState) => void
  ): Promise<number> {
    let updatedCount = 0;

    for (let i = 0; i < cardIds.length; i++) {
      const cardId = cardIds[i];

      // Update progress
      this.progressState[userId] = {
        type: 'progress',
        message: `Updating prices ${i + 1} of ${cardIds.length}`,
        current: i + 1,
        total: cardIds.length,
        phase: 'price_update'
      };

      if (onProgress) onProgress(this.progressState[userId]);

      try {
        const card = await db.getCardById(cardId, userId);
        if (!card) continue;

        const scryfallData = await ScryfallService.searchCard(
          card.card_name,
          card.set_code || undefined,
          card.collector_number || undefined
        );

        if (scryfallData) {
          const currentPrice = parseFloat(
            card.is_foil ? 
            (scryfallData.prices.usd_foil || '0') : 
            (scryfallData.prices.usd || '0')
          );

          const totalValue = currentPrice * card.quantity;
          const priceChange = currentPrice - card.purchase_price;

          await db.updateCard(cardId, {
            current_price: currentPrice,
            total_value: totalValue,
            price_change: priceChange,
            market_url: scryfallData.scryfall_uri,
            image_url: scryfallData.image_uris?.normal,
            image_url_back: scryfallData.card_faces?.[1]?.image_uris?.normal,
            rarity: scryfallData.rarity,
            colors: scryfallData.colors.join(''),
            mana_cost: scryfallData.mana_cost,
            mana_value: scryfallData.mana_value || 0,
            card_type: scryfallData.type_line,
            last_updated: new Date().toISOString()
          });

          updatedCount++;
        }

      } catch (error) {
        console.error(`Error updating card ${cardId}:`, error);
      }

      // Rate limiting delay
      await new Promise(resolve => setTimeout(resolve, 150));
    }

    return updatedCount;
  }

  static async updateSelectedCards(
    cardIds: number[],
    userId: number,
    db: Database,
    onProgress?: (progress: ProgressState) => void
  ): Promise<number> {
    this.progressState[userId] = {
      type: 'start',
      message: `Starting price update for ${cardIds.length} selected cards...`,
      total: cardIds.length,
      current: 0
    };
    this.activeUpdates[userId] = true;

    if (onProgress) onProgress(this.progressState[userId]);

    const updatedCount = await this.updateCardPricesAndMetadataWithProgress(
      cardIds,
      userId,
      db,
      onProgress
    );

    this.progressState[userId] = {
      type: 'complete',
      message: `Successfully updated ${updatedCount} selected cards`,
      updated_count: updatedCount,
      total: cardIds.length
    };

    if (onProgress) onProgress(this.progressState[userId]);

    this.activeUpdates[userId] = false;
    return updatedCount;
  }
}