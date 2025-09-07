import { Router, Request, Response } from 'express';
import { Database } from '../database/database';
import { requireAuth, getCurrentUserId } from '../middleware/auth';
import { ScryfallService } from '../services/scryfall';
import { CSVImportService } from '../services/csvImport';
import multer from 'multer';
import path from 'path';

export function createCardRoutes(db: Database): Router {
  const router = Router();

  // Configure multer for file uploads
  const upload = multer({
    dest: 'uploads/',
    fileFilter: (req, file, cb) => {
      if (file.mimetype === 'text/csv' || path.extname(file.originalname) === '.csv') {
        cb(null, true);
      } else {
        cb(new Error('Only CSV files are allowed'));
      }
    }
  });

  // Progress state storage
  const progressState: { [userId: number]: any } = {};
  const activeUpdates: { [userId: number]: boolean } = {};

  // Dashboard/Index page
  router.get('/', requireAuth, async (req: Request, res: Response) => {
    try {
      const userId = getCurrentUserId(req)!;
      const page = parseInt(req.query.page as string) || 1;
      const perPage = 50;
      const offset = (page - 1) * perPage;

      // Get filter parameters
      const filters = {
        search: req.query.search as string || '',
        rarity: req.query.rarity as string || '',
        color: req.query.color as string || '',
        card_type: req.query.card_type as string || '',
        mana_min: req.query.mana_min as string || '',
        mana_max: req.query.mana_max as string || '',
        sort: req.query.sort as string || 'total_value',
        order: req.query.order as string || 'desc',
        limit: perPage,
        offset: offset
      };

      // Get cards and stats
      const [cards, stats, totalCount, filterOptions] = await Promise.all([
        db.getCards(userId, filters),
        db.getCollectionStats(userId),
        db.getCardCount(userId, filters),
        db.getFilterOptions(userId)
      ]);

      // Pagination
      const totalPages = Math.ceil(totalCount / perPage);
      const pagination = {
        page,
        pages: totalPages,
        total: totalCount,
        has_prev: page > 1,
        has_next: page < totalPages,
        prev_num: page > 1 ? page - 1 : null,
        next_num: page < totalPages ? page + 1 : null
      };

      // Sort colors in WUBRG order
      const sortColorsWubrg = (colors: any[]) => {
        const wubrgOrder = { 'W': 0, 'U': 1, 'B': 2, 'R': 3, 'G': 4 };
        return colors.sort((a, b) => {
          const aStr = a.colors || '';
          const bStr = b.colors || '';
          const aKey = aStr.split('').map((c: string) => wubrgOrder[c as keyof typeof wubrgOrder] ?? 99);
          const bKey = bStr.split('').map((c: string) => wubrgOrder[c as keyof typeof wubrgOrder] ?? 99);
          return aKey.length - bKey.length || aKey.join('').localeCompare(bKey.join(''));
        });
      };

      res.render('index', {
        cards,
        stats,
        pagination,
        current_filters: {
          search: filters.search,
          rarity: filters.rarity,
          color: filters.color,
          card_type: filters.card_type,
          mana_min: filters.mana_min,
          mana_max: filters.mana_max,
          sort: filters.sort,
          order: filters.order
        },
        filtered_count: totalCount,
        active_updates: activeUpdates,
        progress_state: progressState,
        rarities: filterOptions.rarities,
        colors: sortColorsWubrg(filterOptions.colors),
        card_types: filterOptions.cardTypes,
        alerts: [] // TODO: Implement alerts
      });

    } catch (error) {
      console.error('Dashboard error:', error);
      req.flash('error', 'Error loading dashboard');
      res.redirect('/login');
    }
  });

  // Add card page
  router.get('/add_card', requireAuth, (req: Request, res: Response) => {
    res.render('add_card');
  });

  // Add card POST
  router.post('/add_card', requireAuth, async (req: Request, res: Response) => {
    try {
      const userId = getCurrentUserId(req)!;
      const {
        card_name,
        set_name = '',
        set_code = '',
        collector_number = '',
        quantity = 1,
        condition = 'Near Mint',
        purchase_price = 0,
        is_foil = false
      } = req.body;

      if (!card_name?.trim()) {
        req.flash('error', 'Card name is required');
        res.redirect('/add_card');
        return;
      }

      // Check if card already exists
      const existingCards = await db.getCards(userId, { search: card_name, limit: 1 });
      const existingCard = existingCards.find(c =>
        c.card_name === card_name &&
        c.set_code === set_code &&
        c.collector_number === collector_number &&
        c.is_foil === Boolean(is_foil) &&
        c.condition === condition
      );

      if (existingCard && existingCard.id) {
        // Update quantity
        const newQuantity = existingCard.quantity + parseInt(quantity);
        await db.updateCard(existingCard.id, {
          quantity: newQuantity,
          last_updated: new Date().toISOString()
        });

        req.flash('success', `Updated ${card_name} quantity to ${newQuantity} (added ${quantity})`);
        res.redirect('/add_card');
        return;
      }

      // Add new card
      const cardId = await db.addCard({
        card_name: card_name.trim(),
        set_name: set_name.trim(),
        set_code: set_code.trim(),
        collector_number: collector_number.trim(),
        quantity: parseInt(quantity),
        is_foil: Boolean(is_foil),
        condition,
        language: 'English',
        purchase_price: parseFloat(purchase_price),
        current_price: 0,
        price_change: 0,
        total_value: 0,
        mana_value: 0,
        price_alert_threshold: 0,
        last_updated: new Date().toISOString(),
        user_id: userId
      });

      // Background fetch card data
      setTimeout(async () => {
        try {
          const scryfallData = await ScryfallService.searchCard(card_name, set_code, collector_number);
          if (scryfallData) {
            const currentPrice = parseFloat(
              Boolean(is_foil) ?
                (scryfallData.prices.usd_foil || '0') :
                (scryfallData.prices.usd || '0')
            );
            const totalValue = currentPrice * parseInt(quantity);
            const priceChange = currentPrice - parseFloat(purchase_price);

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

            console.log(`Auto-updated card data for: ${card_name}`);
          }
        } catch (error) {
          console.error(`Background card data fetch failed for ${card_name}:`, error);
        }
      }, 100);

      req.flash('success', `Added ${card_name} to your collection (fetching prices and images...)`);
      res.redirect('/add_card');

    } catch (error) {
      console.error('Error adding card:', error);
      req.flash('error', 'Error adding card to collection');
      res.redirect('/add_card');
    }
  });

  // Card detail page
  router.get('/card_detail/:cardId', requireAuth, async (req: Request, res: Response) => {
    try {
      const userId = getCurrentUserId(req)!;
      const cardId = parseInt(req.params.cardId);

      const card = await db.getCardById(cardId, userId);
      if (!card) {
        req.flash('error', 'Card not found');
        res.redirect('/');
        return;
      }

      res.render('card_detail', { card });

    } catch (error) {
      console.error('Card detail error:', error);
      req.flash('error', 'Error loading card details');
      res.redirect('/');
    }
  });

  // Edit card POST
  router.post('/edit_card/:cardId', requireAuth, async (req: Request, res: Response) => {
    try {
      const userId = getCurrentUserId(req)!;
      const cardId = parseInt(req.params.cardId);

      const card = await db.getCardById(cardId, userId);
      if (!card) {
        req.flash('error', 'Card not found');
        res.redirect('/');
        return;
      }

      const {
        quantity = 1,
        condition = 'Near Mint',
        purchase_price = 0,
        alert_threshold = 0
      } = req.body;

      await db.updateCard(cardId, {
        quantity: parseInt(quantity),
        condition,
        purchase_price: parseFloat(purchase_price),
        price_alert_threshold: parseFloat(alert_threshold)
      });

      req.flash('success', 'Card updated successfully');
      res.redirect(`/card_detail/${cardId}`);

    } catch (error) {
      console.error('Error updating card:', error);
      req.flash('error', 'Error updating card');
      res.redirect('/');
    }
  });

  // Delete card POST
  router.post('/delete_card/:cardId', requireAuth, async (req: Request, res: Response) => {
    try {
      const userId = getCurrentUserId(req)!;
      const cardId = parseInt(req.params.cardId);

      const card = await db.getCardById(cardId, userId);
      if (!card) {
        req.flash('error', 'Card not found');
        res.redirect('/');
        return;
      }

      await db.deleteCard(cardId, userId);
      req.flash('success', 'Card deleted successfully');
      res.redirect('/');

    } catch (error) {
      console.error('Error deleting card:', error);
      req.flash('error', 'Error deleting card');
      res.redirect('/');
    }
  });

  // Import CSV
  router.post('/import_csv', requireAuth, upload.single('csv_file'), async (req: Request, res: Response) => {
    try {
      const userId = getCurrentUserId(req)!;

      if (!req.file) {
        req.flash('error', 'No file uploaded');
        res.redirect('/');
        return;
      }

      // Start background import
      setTimeout(async () => {
        try {
          await CSVImportService.importCSV(req.file!.path, userId, db);
        } catch (error) {
          console.error('CSV import error:', error);
        }
      }, 100);

      req.flash('success', 'CSV import started! Progress will be shown below.');
      res.redirect('/');

    } catch (error) {
      console.error('CSV import error:', error);
      req.flash('error', 'Error importing CSV file');
      res.redirect('/');
    }
  });

  // Progress status API
  router.get('/progress_status', requireAuth, (req: Request, res: Response) => {
    const userId = getCurrentUserId(req)!;
    const isActive = activeUpdates[userId] || false;
    const latestProgress = progressState[userId] || null;

    res.json({
      active: isActive,
      latest_progress: latestProgress
    });
  });

  // Collections page
  router.get('/collections', requireAuth, (req: Request, res: Response) => {
    res.render('collections', { templates: [], user_collections: [] });
  });

  // Alerts page
  router.get('/alerts', requireAuth, (req: Request, res: Response) => {
    res.render('alerts', { alerts: [] });
  });

  return router;
}