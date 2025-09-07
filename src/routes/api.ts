import { Router, Request, Response } from 'express';
import { Database } from '../database/database';
import { requireAuth, getCurrentUserId } from '../middleware/auth';
import { ScryfallService } from '../services/scryfall';
import { CSVImportService } from '../services/csvImport';

export function createApiRoutes(db: Database): Router {
  const router = Router();

  // Search cards API (for autocomplete)
  router.get('/search_cards', requireAuth, async (req: Request, res: Response) => {
    try {
      const query = req.query.q as string;

      if (!query || query.length < 2) {
        res.json([]);
        return;
      }

      const results = await ScryfallService.searchCardsFuzzy(query);

      // Transform for frontend
      const transformedResults = results.map(card => ({
        name: card.name,
        set_name: card.set_name,
        set: card.set,
        collector_number: card.collector_number,
        rarity: card.rarity,
        mana_cost: card.mana_cost,
        type_line: card.type_line,
        colors: card.colors.join(','),
        image_url: card.image_uris?.small || '',
        prices: card.prices
      }));

      res.json(transformedResults);

    } catch (error) {
      console.error('Card search error:', error);
      res.json([]);
    }
  });

  // Get cards API
  router.get('/cards', requireAuth, async (req: Request, res: Response) => {
    try {
      const userId = getCurrentUserId(req)!;
      const cards = await db.getCards(userId, { sort: 'total_value', order: 'desc' });

      const cardsData = cards.map(card => ({
        id: card.id,
        card_name: card.card_name,
        set_name: card.set_name,
        current_price: card.current_price || 0,
        total_value: card.total_value || 0,
        price_change: card.price_change || 0
      }));

      res.json(cardsData);

    } catch (error) {
      console.error('API cards error:', error);
      res.status(500).json({ error: 'Failed to fetch cards' });
    }
  });

  // Get card image API
  router.get('/card/:cardId/image', requireAuth, async (req: Request, res: Response) => {
    try {
      const userId = getCurrentUserId(req)!;
      const cardId = parseInt(req.params.cardId);

      const card = await db.getCardById(cardId, userId);

      if (card && card.image_url) {
        res.json({ image_url: card.image_url });
      } else {
        res.json({ image_url: null });
      }

    } catch (error) {
      console.error('API card image error:', error);
      res.status(500).json({ error: 'Failed to fetch card image' });
    }
  });

  // Delete all cards
  router.post('/delete_all_cards', requireAuth, async (req: Request, res: Response) => {
    try {
      const userId = getCurrentUserId(req)!;

      // Get count before deletion
      const totalCards = await db.getCardCount(userId);

      if (totalCards === 0) {
        res.json({ success: false, error: 'No cards to delete' });
        return;
      }

      // Delete all cards for this user
      const cards = await db.getCards(userId);
      for (const card of cards) {
        if (card.id) {
          await db.deleteCard(card.id, userId);
        }
      }

      res.json({
        success: true,
        message: `Successfully deleted ${totalCards} cards from your collection`,
        deleted_count: totalCards
      });

    } catch (error) {
      console.error('Error deleting all cards:', error);
      res.json({ success: false, error: 'Failed to delete cards' });
    }
  });

  // Mass delete cards
  router.post('/mass_delete', requireAuth, async (req: Request, res: Response) => {
    try {
      const userId = getCurrentUserId(req)!;
      const { card_ids } = req.body;

      if (!card_ids || !Array.isArray(card_ids) || card_ids.length === 0) {
        res.json({ success: false, error: 'No cards selected' });
        return;
      }

      let deletedCount = 0;

      // Verify and delete cards
      for (const cardId of card_ids) {
        try {
          const card = await db.getCardById(parseInt(cardId), userId);
          if (card && card.id) {
            await db.deleteCard(card.id, userId);
            deletedCount++;
          }
        } catch (error) {
          console.error(`Error deleting card ${cardId}:`, error);
        }
      }

      res.json({
        success: true,
        deleted_count: deletedCount,
        message: `Successfully deleted ${deletedCount} cards`
      });

    } catch (error) {
      console.error('Error in mass delete:', error);
      res.json({ success: false, error: 'Failed to delete cards' });
    }
  });

  // Mass update prices
  router.post('/mass_update_prices', requireAuth, async (req: Request, res: Response) => {
    try {
      const userId = getCurrentUserId(req)!;
      const { card_ids } = req.body;

      if (!card_ids || !Array.isArray(card_ids) || card_ids.length === 0) {
        res.json({ success: false, error: 'No cards selected' });
        return;
      }

      // Start background update
      setTimeout(async () => {
        try {
          await CSVImportService.updateSelectedCards(
            card_ids.map((id: string) => parseInt(id)),
            userId,
            db
          );
        } catch (error) {
          console.error('Mass price update error:', error);
        }
      }, 100);

      res.json({
        success: true,
        message: `Started price update for ${card_ids.length} cards`
      });

    } catch (error) {
      console.error('Error starting mass update:', error);
      res.json({ success: false, error: 'Failed to start price update' });
    }
  });

  return router;
}