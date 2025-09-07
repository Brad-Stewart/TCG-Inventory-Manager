@app.route('/import_csv', methods=['POST'])
@login_required
def import_csv():
    """Import CSV file to database with background processing and progress tracking"""
    current_user_id = get_current_user_id()
    
    # Get template creation options
    create_template = request.form.get('create_template', False)
    template_name = request.form.get('template_name', '')
    make_public = request.form.get('make_public', False)
    
    # Read CSV file
    df = None
    try:
        # Check if file was uploaded
        if 'csv_file' in request.files:
            file = request.files['csv_file']
            if file.filename:
                df = pd.read_csv(file)
                logger.info(f"CSV uploaded with {len(df)} rows and columns: {list(df.columns)}")
            else:
                flash('No file selected')
                return redirect(url_for('index'))
        else:
            # Fallback to file path
            csv_path = request.form.get('csv_path')
            if not csv_path:
                flash('No CSV file provided')
                return redirect(url_for('index'))
            
            df = pd.read_csv(csv_path)
            logger.info(f"CSV loaded from path: {csv_path}")
            
    except Exception as e:
        flash(f'Error reading CSV file: {e}')
        return redirect(url_for('index'))
    
    if df is None or len(df) == 0:
        flash('CSV file is empty or could not be read')
        return redirect(url_for('index'))
    
    # Start background import process
    def background_csv_import(dataframe, user_id, create_tmpl, tmpl_name, make_pub):
        """Background CSV import with progress tracking and auto-price updates"""
        try:
            from csv_import_helpers import preprocess_csv_data, import_cards_with_progress, update_card_prices_and_metadata_with_progress
            
            # Initialize progress
            progress_state[user_id] = {
                'type': 'start',
                'total': len(dataframe),
                'message': f'Starting import of {len(dataframe)} cards...',
                'phase': 'preprocessing'
            }
            
            # Process CSV data
            df_processed = preprocess_csv_data(dataframe, user_id)
            
            # Import cards with progress tracking
            imported_count, imported_card_ids = import_cards_with_progress(df_processed, user_id, progress_state)
            
            # Auto-update prices and metadata
            updated_count = 0
            if imported_card_ids:
                progress_state[user_id] = {
                    'type': 'progress',
                    'message': f'Fetching prices and images for {len(imported_card_ids)} cards...',
                    'phase': 'price_update',
                    'current': 0,
                    'total': len(imported_card_ids)
                }
                
                updated_count = update_card_prices_and_metadata_with_progress(imported_card_ids, user_id, progress_state)
            
            # Create template if requested
            template_id = None
            if create_tmpl and tmpl_name:
                try:
                    template_id = create_collection_template(
                        df=df_processed,
                        template_name=tmpl_name,
                        description=f"Collection imported from CSV with {imported_count} cards",
                        user_id=user_id,
                        make_public=bool(make_pub)
                    )
                except Exception as e:
                    logger.error(f"Template creation failed: {e}")
            
            # Final completion message
            template_msg = f" Template '{tmpl_name}' created." if template_id else ""
            progress_state[user_id] = {
                'type': 'complete',
                'message': f'Successfully imported {imported_count} cards with {updated_count} price updates.{template_msg}',
                'imported_count': imported_count,
                'updated_count': updated_count,
                'total': len(dataframe)
            }
            
            # Clean up
            active_updates[user_id] = False
            
        except Exception as e:
            logger.error(f"CSV import error: {e}")
            progress_state[user_id] = {
                'type': 'error',
                'message': f'Import failed: {str(e)}',
                'error': str(e)
            }
            active_updates[user_id] = False
    
    # Mark import as active and start background thread
    active_updates[current_user_id] = True
    threading.Thread(target=background_csv_import, args=(df, current_user_id, create_template, template_name, make_public), daemon=True).start()
    
    flash('CSV import started! Progress will be shown below.')
    return redirect(url_for('index'))