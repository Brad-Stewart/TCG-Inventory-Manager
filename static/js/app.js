// JavaScript for PackRat

document.addEventListener('DOMContentLoaded', function() {
    // Auto-refresh functionality
    setupAutoRefresh();
    
    // Price update loading states
    setupPriceUpdateLoading();
    
    // Card search and filtering
    setupCardFiltering();
    
    // Alert management
    setupAlertManagement();
    
    // Card preview functionality
    setupCardPreviews();
    
    // Mass editing functionality
    setupMassEditing();
    
    // Progress tracking
    setupProgressTracking();
    
    // Template creation options
    setupTemplateCreation();
    
    // Card autocomplete
    setupCardAutocomplete();
});

function setupAutoRefresh() {
    // Auto-refresh prices every 5 minutes if enabled
    const autoRefreshEnabled = localStorage.getItem('autoRefresh') === 'true';
    
    if (autoRefreshEnabled) {
        setInterval(function() {
            fetch('/api/cards')
                .then(response => response.json())
                .then(data => {
                    updateCardPricesInTable(data);
                })
                .catch(error => console.error('Auto-refresh error:', error));
        }, 300000); // 5 minutes
    }
}

function setupPriceUpdateLoading() {
    const updatePricesBtn = document.querySelector('a[href*="update_prices"]');
    
    if (updatePricesBtn) {
        updatePricesBtn.addEventListener('click', function(e) {
            this.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Updating Prices...';
            this.classList.add('disabled');
        });
    }
}

function setupCardFiltering() {
    // Add search functionality to the inventory table
    const searchInput = document.createElement('input');
    searchInput.type = 'text';
    searchInput.className = 'form-control mb-3';
    searchInput.placeholder = 'Search cards...';
    searchInput.id = 'cardSearch';
    
    const tableContainer = document.querySelector('.table-responsive');
    if (tableContainer) {
        tableContainer.parentNode.insertBefore(searchInput, tableContainer);
        
        searchInput.addEventListener('input', function() {
            filterCards(this.value.toLowerCase());
        });
    }
}

function filterCards(searchTerm) {
    const tableRows = document.querySelectorAll('tbody tr');
    
    tableRows.forEach(row => {
        const cardName = row.cells[0].textContent.toLowerCase();
        const setName = row.cells[1].textContent.toLowerCase();
        
        if (cardName.includes(searchTerm) || setName.includes(searchTerm)) {
            row.style.display = '';
        } else {
            row.style.display = 'none';
        }
    });
}

function setupAlertManagement() {
    // Add alert notification counter
    const alertsLink = document.querySelector('a[href*="alerts"]');
    if (alertsLink) {
        fetch('/api/cards')
            .then(response => response.json())
            .then(data => {
                // This would need an API endpoint for unread alerts count
                // For now, just add basic styling
                const unreadAlerts = document.querySelectorAll('.alert:not(.alert-secondary)').length;
                if (unreadAlerts > 0) {
                    alertsLink.innerHTML += ` <span class="badge bg-warning">${unreadAlerts}</span>`;
                }
            })
            .catch(error => console.error('Alert check error:', error));
    }
}

function updateCardPricesInTable(cardsData) {
    // Update price display in the main table
    const tableRows = document.querySelectorAll('tbody tr');
    
    tableRows.forEach((row, index) => {
        if (cardsData[index]) {
            const card = cardsData[index];
            
            // Update current price
            const priceCell = row.cells[4];
            priceCell.textContent = `$${card.current_price.toFixed(2)}`;
            
            // Update total value
            const valueCell = row.cells[5];
            valueCell.textContent = `$${card.total_value.toFixed(2)}`;
            
            // Update price change with color coding
            const changeCell = row.cells[6];
            const change = card.price_change;
            
            if (change > 0) {
                changeCell.innerHTML = `<span class="text-success">+$${change.toFixed(2)}</span>`;
            } else if (change < 0) {
                changeCell.innerHTML = `<span class="text-danger">$${change.toFixed(2)}</span>`;
            } else {
                changeCell.innerHTML = `<span class="text-muted">$0.00</span>`;
            }
        }
    });
}

// Utility functions
function formatCurrency(amount) {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD'
    }).format(amount);
}

function showLoading(element) {
    element.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Loading...';
    element.classList.add('disabled');
}

function hideLoading(element, originalText) {
    element.innerHTML = originalText;
    element.classList.remove('disabled');
}

// Auto-save for card editing
function setupAutoSave() {
    const editForm = document.querySelector('form[action*="edit_card"]');
    
    if (editForm) {
        const inputs = editForm.querySelectorAll('input, select');
        
        inputs.forEach(input => {
            input.addEventListener('change', function() {
                // Debounced auto-save
                clearTimeout(this.saveTimeout);
                this.saveTimeout = setTimeout(() => {
                    saveCardChanges(editForm);
                }, 1000);
            });
        });
    }
}

function saveCardChanges(form) {
    const formData = new FormData(form);
    
    fetch(form.action, {
        method: 'POST',
        body: formData
    })
    .then(response => {
        if (response.ok) {
            showToast('Changes saved automatically', 'success');
        }
    })
    .catch(error => {
        console.error('Auto-save error:', error);
        showToast('Auto-save failed', 'error');
    });
}

function showToast(message, type = 'info') {
    // Simple toast notification
    const toast = document.createElement('div');
    toast.className = `alert alert-${type === 'error' ? 'danger' : type} position-fixed`;
    toast.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
    toast.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.body.appendChild(toast);
    
    // Auto-remove after 3 seconds
    setTimeout(() => {
        if (toast.parentNode) {
            toast.remove();
        }
    }, 3000);
}

function analyzeCSV() {
    const fileInput = document.getElementById('csv_file');
    
    if (!fileInput.files[0]) {
        alert('Please select a CSV file first');
        return;
    }
    
    const formData = new FormData();
    formData.append('csv_file', fileInput.files[0]);
    
    fetch('/analyze_csv', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            alert('Error: ' + data.error);
            return;
        }
        
        // Display CSV analysis
        let analysisHTML = `
            <div class="modal fade" id="csvAnalysisModal" tabindex="-1">
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">CSV Analysis</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <p><strong>Total Rows:</strong> ${data.total_rows}</p>
                            <p><strong>Columns Found:</strong> ${data.columns.length}</p>
                            <div class="table-responsive">
                                <table class="table table-sm">
                                    <thead>
                                        <tr>
                                            <th>Column Name</th>
                                            <th>Data Type</th>
                                            <th>Sample Data</th>
                                        </tr>
                                    </thead>
                                    <tbody>
        `;
        
        data.columns.forEach(col => {
            analysisHTML += `
                <tr>
                    <td><code>${col}</code></td>
                    <td>${data.data_types[col]}</td>
                    <td>${data.sample_data[col].slice(0, 3).join(', ')}</td>
                </tr>
            `;
        });
        
        analysisHTML += `
                                    </tbody>
                                </table>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // Remove existing modal if present
        const existingModal = document.getElementById('csvAnalysisModal');
        if (existingModal) {
            existingModal.remove();
        }
        
        // Add new modal
        document.body.insertAdjacentHTML('beforeend', analysisHTML);
        
        // Show modal
        const modal = new bootstrap.Modal(document.getElementById('csvAnalysisModal'));
        modal.show();
    })
    .catch(error => {
        alert('Error analyzing CSV: ' + error);
    });
}

function quickUpdateRarity() {
    const fileInput = document.getElementById('csv_file');
    
    if (!fileInput || !fileInput.files[0]) {
        // Create a temporary file input
        const tempInput = document.createElement('input');
        tempInput.type = 'file';
        tempInput.accept = '.csv';
        tempInput.onchange = function() {
            if (this.files[0]) {
                const formData = new FormData();
                formData.append('csv_file', this.files[0]);
                
                fetch('/update_rarity_from_csv', {
                    method: 'POST',
                    body: formData
                })
                .then(response => {
                    if (response.ok) {
                        location.reload();
                    } else {
                        alert('Error updating rarity data');
                    }
                })
                .catch(error => {
                    alert('Error: ' + error);
                });
            }
        };
        tempInput.click();
    } else {
        // Use existing file
        const formData = new FormData();
        formData.append('csv_file', fileInput.files[0]);
        
        fetch('/update_rarity_from_csv', {
            method: 'POST',
            body: formData
        })
        .then(response => {
            if (response.ok) {
                location.reload();
            } else {
                alert('Error updating rarity data');
            }
        })
        .catch(error => {
            alert('Error: ' + error);
        });
    }
}

function setupCardImageHover() {
    // Create image preview tooltip
    const imagePreview = document.createElement('div');
    imagePreview.id = 'cardImagePreview';
    imagePreview.style.cssText = `
        position: absolute;
        z-index: 9999;
        pointer-events: none;
        background: white;
        border: 2px solid #333;
        border-radius: 8px;
        padding: 5px;
        box-shadow: 0 4px 8px rgba(0,0,0,0.3);
        display: none;
        max-width: 300px;
    `;
    document.body.appendChild(imagePreview);
    
    // Add hover events to all card names
    const cardNameCells = document.querySelectorAll('tbody tr td:first-child strong');
    
    cardNameCells.forEach(cardNameElement => {
        const cardRow = cardNameElement.closest('tr');
        const cardId = cardRow.querySelector('a[href*="/card/"]').href.split('/').pop();
        
        cardNameElement.style.cursor = 'pointer';
        cardNameElement.style.textDecoration = 'underline';
        cardNameElement.style.color = '#0d6efd';
        
        cardNameElement.addEventListener('mouseenter', function(e) {
            // Fetch card image URL from API
            fetch(`/api/card/${cardId}/image`)
                .then(response => response.json())
                .then(data => {
                    if (data.image_url) {
                        const img = document.createElement('img');
                        img.src = data.image_url;
                        img.style.cssText = 'max-width: 280px; height: auto; border-radius: 5px;';
                        img.onload = function() {
                            imagePreview.innerHTML = '';
                            imagePreview.appendChild(img);
                            imagePreview.style.display = 'block';
                            updatePreviewPosition(e);
                        };
                        img.onerror = function() {
                            imagePreview.innerHTML = '<div style="padding: 10px; color: #666;">No image available</div>';
                            imagePreview.style.display = 'block';
                            updatePreviewPosition(e);
                        };
                    } else {
                        imagePreview.innerHTML = '<div style="padding: 10px; color: #666;">No image available</div>';
                        imagePreview.style.display = 'block';
                        updatePreviewPosition(e);
                    }
                })
                .catch(error => {
                    console.error('Error fetching card image:', error);
                    imagePreview.innerHTML = '<div style="padding: 10px; color: #666;">Image unavailable</div>';
                    imagePreview.style.display = 'block';
                    updatePreviewPosition(e);
                });
        });
        
        cardNameElement.addEventListener('mouseleave', function() {
            imagePreview.style.display = 'none';
        });
        
        cardNameElement.addEventListener('mousemove', function(e) {
            if (imagePreview.style.display === 'block') {
                updatePreviewPosition(e);
            }
        });
    });
    
    function updatePreviewPosition(e) {
        const x = e.pageX + 15;
        const y = e.pageY + 15;
        
        // Ensure preview doesn't go off screen
        const previewRect = imagePreview.getBoundingClientRect();
        const windowWidth = window.innerWidth;
        const windowHeight = window.innerHeight;
        
        let finalX = x;
        let finalY = y;
        
        if (x + previewRect.width > windowWidth) {
            finalX = e.pageX - previewRect.width - 15;
        }
        
        if (y + previewRect.height > windowHeight + window.scrollY) {
            finalY = e.pageY - previewRect.height - 15;
        }
        
        imagePreview.style.left = finalX + 'px';
        imagePreview.style.top = finalY + 'px';
    }
}

function setupMassEditing() {
    const selectAllCheckbox = document.getElementById('selectAll');
    const cardCheckboxes = document.querySelectorAll('.card-checkbox');
    const massActionPanel = document.getElementById('massActionPanel');
    const selectedCountSpan = document.getElementById('selectedCount');
    
    // Select/deselect all functionality
    if (selectAllCheckbox) {
        selectAllCheckbox.addEventListener('change', function() {
            cardCheckboxes.forEach(checkbox => {
                checkbox.checked = this.checked;
            });
            updateMassActionPanel();
        });
    }
    
    // Individual checkbox change
    cardCheckboxes.forEach(checkbox => {
        checkbox.addEventListener('change', function() {
            updateMassActionPanel();
            
            // Update select all checkbox state
            const checkedBoxes = document.querySelectorAll('.card-checkbox:checked');
            if (selectAllCheckbox) {
                selectAllCheckbox.checked = checkedBoxes.length === cardCheckboxes.length;
                selectAllCheckbox.indeterminate = checkedBoxes.length > 0 && checkedBoxes.length < cardCheckboxes.length;
            }
        });
    });
    
    function updateMassActionPanel() {
        const checkedBoxes = document.querySelectorAll('.card-checkbox:checked');
        const count = checkedBoxes.length;
        
        if (count > 0) {
            massActionPanel.style.display = 'block';
            selectedCountSpan.textContent = `${count} card${count > 1 ? 's' : ''} selected`;
        } else {
            massActionPanel.style.display = 'none';
        }
    }
}

function getSelectedCardIds() {
    const checkedBoxes = document.querySelectorAll('.card-checkbox:checked');
    return Array.from(checkedBoxes).map(checkbox => checkbox.value);
}

function clearSelection() {
    const cardCheckboxes = document.querySelectorAll('.card-checkbox');
    const selectAllCheckbox = document.getElementById('selectAll');
    
    cardCheckboxes.forEach(checkbox => {
        checkbox.checked = false;
    });
    
    if (selectAllCheckbox) {
        selectAllCheckbox.checked = false;
        selectAllCheckbox.indeterminate = false;
    }
    
    document.getElementById('massActionPanel').style.display = 'none';
}

function massUpdatePrices() {
    const selectedIds = getSelectedCardIds();
    
    if (selectedIds.length === 0) {
        alert('Please select cards to update');
        return;
    }
    
    if (confirm(`Update prices for ${selectedIds.length} selected cards?`)) {
        showToast(`Updating prices for ${selectedIds.length} cards...`, 'info');
        
        fetch('/mass_update_prices', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({card_ids: selectedIds})
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showToast(`Updated ${data.updated_count} cards successfully`, 'success');
                setTimeout(() => location.reload(), 2000);
            } else {
                showToast(`Error: ${data.error}`, 'error');
            }
        })
        .catch(error => {
            showToast(`Error updating prices: ${error}`, 'error');
        });
    }
}

function massDelete() {
    const selectedIds = getSelectedCardIds();
    
    if (selectedIds.length === 0) {
        alert('Please select cards to delete');
        return;
    }
    
    if (confirm(`Are you sure you want to delete ${selectedIds.length} selected cards? This action cannot be undone.`)) {
        fetch('/mass_delete', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({card_ids: selectedIds})
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showToast(`Deleted ${data.deleted_count} cards successfully`, 'success');
                setTimeout(() => location.reload(), 1500);
            } else {
                showToast(`Error: ${data.error}`, 'error');
            }
        })
        .catch(error => {
            showToast(`Error deleting cards: ${error}`, 'error');
        });
    }
}

function deleteAllCards() {
    const confirmation = confirm('⚠️ WARNING: This will delete ALL cards in your collection!\n\nThis action cannot be undone. Are you absolutely sure?');
    
    if (!confirmation) {
        return;
    }
    
    const doubleConfirmation = confirm('This is your last chance!\n\nType YES in the next prompt to confirm deletion of your entire collection.');
    
    if (!doubleConfirmation) {
        return;
    }
    
    const finalConfirm = prompt('Type "DELETE ALL" (without quotes) to confirm:');
    
    if (finalConfirm !== 'DELETE ALL') {
        alert('Deletion cancelled - confirmation text did not match.');
        return;
    }
    
    fetch('/delete_all_cards', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast(data.message, 'success');
            setTimeout(() => location.reload(), 2000);
        } else {
            showToast(data.error, 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showToast('Error deleting collection', 'error');
    });
}

// Card preview functionality
function setupCardPreviews() {
    // Create overlay elements
    const backdrop = document.createElement('div');
    backdrop.className = 'card-preview-backdrop';
    document.body.appendChild(backdrop);
    
    const largePreview = document.createElement('img');
    largePreview.className = 'card-preview-large';
    document.body.appendChild(largePreview);
    
    let currentPreviewTimeout;
    
    // Handle small preview images
    document.querySelectorAll('.card-preview-small').forEach(img => {
        img.addEventListener('mouseenter', function() {
            showLargePreview(this.dataset.imageUrl, this.dataset.cardName);
        });
        
        img.addEventListener('mouseleave', function() {
            hideLargePreview();
        });
    });
    
    // Handle placeholder icons (cards without images)
    document.querySelectorAll('.card-preview-placeholder').forEach(placeholder => {
        placeholder.addEventListener('mouseenter', function() {
            const cardName = this.dataset.cardName;
            const cardId = this.dataset.cardId;
            
            // Try to fetch image from API
            fetch(`/api/card/${cardId}/image`)
                .then(response => response.json())
                .then(data => {
                    if (data.image_url) {
                        showLargePreview(data.image_url, cardName);
                        // Update the placeholder with the actual image
                        const img = document.createElement('img');
                        img.src = data.image_url;
                        img.className = 'card-preview-small';
                        img.alt = cardName;
                        img.dataset.cardName = cardName;
                        img.dataset.imageUrl = data.image_url;
                        
                        // Replace placeholder with image
                        this.parentNode.replaceChild(img, this);
                        setupCardPreview(img);
                    } else {
                        showNoImageMessage(cardName);
                    }
                })
                .catch(error => {
                    console.error('Error fetching card image:', error);
                    showNoImageMessage(cardName);
                });
        });
        
        placeholder.addEventListener('mouseleave', function() {
            hideLargePreview();
        });
    });
    
    function showLargePreview(imageUrl, cardName) {
        clearTimeout(currentPreviewTimeout);
        
        largePreview.src = imageUrl;
        largePreview.alt = cardName;
        
        backdrop.classList.add('show');
        largePreview.classList.add('show');
    }
    
    function showNoImageMessage(cardName) {
        clearTimeout(currentPreviewTimeout);
        
        // Remove any existing no-image message
        const existingMessage = document.querySelector('.no-image-message');
        if (existingMessage) {
            document.body.removeChild(existingMessage);
        }
        
        // Create a temporary message element
        const messageDiv = document.createElement('div');
        messageDiv.className = 'card-preview-large show no-image-message';
        messageDiv.style.background = '#fff';
        messageDiv.style.padding = '20px';
        messageDiv.style.textAlign = 'center';
        messageDiv.style.color = '#666';
        messageDiv.innerHTML = `<i class="fas fa-image fa-2x mb-2"></i><br>No image available for<br><strong>${cardName}</strong>`;
        
        document.body.appendChild(messageDiv);
        backdrop.classList.add('show');
        
        // Store reference to the message div for cleanup
        messageDiv._isNoImageMessage = true;
    }
    
    function hideLargePreview() {
        clearTimeout(currentPreviewTimeout);
        
        currentPreviewTimeout = setTimeout(() => {
            backdrop.classList.remove('show');
            largePreview.classList.remove('show');
            
            // Clean up any no-image message
            const existingMessage = document.querySelector('.no-image-message');
            if (existingMessage) {
                existingMessage.classList.remove('show');
                setTimeout(() => {
                    if (existingMessage.parentNode) {
                        document.body.removeChild(existingMessage);
                    }
                }, 200); // Wait for CSS transition
            }
        }, 100);
    }
    
    function setupCardPreview(img) {
        img.addEventListener('mouseenter', function() {
            showLargePreview(this.dataset.imageUrl, this.dataset.cardName);
        });
        
        img.addEventListener('mouseleave', function() {
            hideLargePreview();
        });
    }
    
    // Hide preview when clicking anywhere
    backdrop.addEventListener('click', hideLargePreview);
}

// Enhanced progress tracking that persists across page loads
function setupProgressTracking() {
    // Small delay to ensure page is fully loaded
    setTimeout(() => {
        // First check if there's an active operation by polling the server
        checkForActiveOperations();
        
        // Also check for flash messages (for newly started operations)
        const flashMessages = document.querySelectorAll('.alert');
        let hasActiveUpdate = false;
        
        flashMessages.forEach(msg => {
            if (msg.textContent.includes('Started background price update') || 
                msg.textContent.includes('Check progress below') ||
                msg.textContent.includes('CSV import started') ||
                msg.textContent.includes('Progress will be shown below') ||
                msg.textContent.includes('Price update started')) {
                hasActiveUpdate = true;
            }
        });
        
        if (hasActiveUpdate) {
            startSimplePolling();
        }
    }, 100);
}

function checkForActiveOperations() {
    // Check server for any active operations
    fetch('/progress_status')
        .then(response => {
            if (!response.ok) {
                return; // User not logged in or other error
            }
            return response.json();
        })
        .then(data => {
            if (data && data.active) {
                // There's an active operation, start polling
                startSimplePolling();
            }
        })
        .catch(error => {
            // Silently fail - user might not be logged in
            console.debug('Could not check for active operations:', error);
        });
}

// Enhanced polling that persists across page loads
function startSimplePolling() {
    const progressContainer = document.getElementById('progressContainer');
    const progressBar = document.getElementById('progressBar');
    const progressMessage = document.getElementById('progressMessage');
    const currentCardEl = document.getElementById('currentCard');
    const totalCardsEl = document.getElementById('totalCards');
    const updatedCountEl = document.getElementById('updatedCount');
    const errorCountEl = document.getElementById('errorCount');
    const cardNameEl = document.getElementById('cardName');
    
    // Don't start polling if it's already running
    if (window.progressPolling) {
        return;
    }
    
    // Show progress container
    if (progressContainer) {
        progressContainer.style.display = 'block';
    }
    
    let pollInterval;
    let lastProgress = null;
    let errorCount = 0;
    
    // Mark polling as active
    window.progressPolling = true;
    
    function pollProgress() {
        fetch('/progress_status')
            .then(response => {
                if (!response.ok) {
                    if (response.status === 401 || response.status === 302) {
                        throw new Error('Authentication required');
                    }
                    throw new Error(`HTTP ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                if (!data.active) {
                    if (progressMessage) {
                        progressMessage.innerHTML = '<span class="text-info"><i class="fas fa-check-circle"></i> Operation completed.</span>';
                    }
                    clearInterval(pollInterval);
                    window.progressPolling = false;
                    setTimeout(() => {
                        if (progressContainer) {
                            progressContainer.style.display = 'none';
                        }
                        // Only reload if we're still on the same page
                        if (!document.hidden) {
                            location.reload();
                        }
                    }, 3000);
                    return;
                }
                
                if (data.latest_progress) {
                    const progress = data.latest_progress;
                    
                    switch(progress.type) {
                        case 'start':
                            totalCardsEl.textContent = progress.total;
                            progressMessage.innerHTML = '<span class="text-info"><i class="fas fa-clock"></i> ' + progress.message + '</span>';
                            break;
                            
                        case 'progress':
                            const percentage = Math.round((progress.current / progress.total) * 100);
                            progressBar.style.width = percentage + '%';
                            progressBar.textContent = percentage + '%';
                            progressBar.setAttribute('aria-valuenow', percentage);
                            
                            currentCardEl.textContent = progress.current;
                            totalCardsEl.textContent = progress.total;
                            cardNameEl.textContent = progress.card_name;
                            progressMessage.innerHTML = '<span class="text-primary"><i class="fas fa-sync-alt fa-spin"></i> ' + progress.message + '</span>';
                            
                            // Use the updated_count from backend
                            updatedCountEl.textContent = progress.updated_count || progress.current;
                            break;
                            
                        case 'complete':
                            if (progressBar) {
                                progressBar.style.width = '100%';
                                progressBar.textContent = '100%';
                                progressBar.classList.remove('progress-bar-animated');
                            }
                            if (progressMessage) {
                                progressMessage.innerHTML = `<span class="text-success"><i class="fas fa-check-circle"></i> ${progress.message}</span>`;
                            }
                            if (cardNameEl) {
                                cardNameEl.textContent = 'Complete!';
                            }
                            
                            clearInterval(pollInterval);
                            window.progressPolling = false;
                            setTimeout(() => {
                                if (progressContainer) {
                                    progressContainer.style.display = 'none';
                                }
                                // Only reload if we're still on the same page
                                if (!document.hidden) {
                                    location.reload();
                                }
                            }, 5000);
                            break;
                            
                        case 'error':
                            errorCount++;
                            errorCountEl.textContent = errorCount;
                            break;
                    }
                } else {
                    // No progress data yet
                    progressMessage.innerHTML = '<span class="text-muted"><i class="fas fa-hourglass-half"></i> Waiting for price update to start...</span>';
                }
            })
            .catch(error => {
                console.error('Polling error:', error);
                if (progressMessage) {
                    if (error.message === 'Authentication required') {
                        progressMessage.innerHTML = '<span class="text-warning"><i class="fas fa-user-lock"></i> Session expired. Please refresh the page to continue tracking.</span>';
                    } else {
                        progressMessage.innerHTML = '<span class="text-danger"><i class="fas fa-exclamation-triangle"></i> Connection error. Please refresh the page.</span>';
                    }
                }
                clearInterval(pollInterval);
                window.progressPolling = false;
            });
    }
    
    // Start polling every 2 seconds
    progressMessage.innerHTML = '<span class="text-info"><i class="fas fa-satellite-dish"></i> Starting progress tracking...</span>';
    pollInterval = setInterval(pollProgress, 2000);
    
    // Initial poll
    pollProgress();
    
    // Clean up on page unload
    window.addEventListener('beforeunload', function() {
        if (pollInterval) {
            clearInterval(pollInterval);
            window.progressPolling = false;
        }
    });
}

function setupTemplateCreation() {
    const createTemplateCheckbox = document.getElementById('create_template');
    const templateOptions = document.getElementById('template_options');
    
    if (createTemplateCheckbox && templateOptions) {
        createTemplateCheckbox.addEventListener('change', function() {
            if (this.checked) {
                templateOptions.style.display = 'block';
                // Make template name required when checkbox is checked
                document.getElementById('template_name').setAttribute('required', 'required');
            } else {
                templateOptions.style.display = 'none';
                // Remove required attribute when checkbox is unchecked
                document.getElementById('template_name').removeAttribute('required');
            }
        });
    }
}

function setupCardAutocomplete() {
    const cardNameInput = document.getElementById('card_name');
    const suggestionsContainer = document.getElementById('card_suggestions');
    const loadingSpinner = document.getElementById('search_loading');
    
    if (!cardNameInput || !suggestionsContainer) return;
    
    let searchTimeout;
    let currentHighlight = -1;
    let suggestions = [];
    
    // Debounced search function
    function searchCards(query) {
        if (query.length < 2) {
            hideSuggestions();
            return;
        }
        
        showLoading();
        
        fetch(`/api/search_cards?q=${encodeURIComponent(query)}`)
            .then(response => response.json())
            .then(cards => {
                hideLoading();
                suggestions = cards;
                displaySuggestions(cards);
                currentHighlight = -1;
            })
            .catch(error => {
                console.error('Card search error:', error);
                hideLoading();
                hideSuggestions();
            });
    }
    
    function displaySuggestions(cards) {
        if (cards.length === 0) {
            hideSuggestions();
            return;
        }
        
        let html = '';
        cards.forEach((card, index) => {
            const imageHtml = card.image_url 
                ? `<img src="${card.image_url}" class="suggestion-image" alt="${card.name}">`
                : `<div class="suggestion-image-placeholder"><i class="fas fa-image"></i></div>`;
            
            const rarityClass = card.rarity.toLowerCase();
            const price = card.prices.usd ? `$${card.prices.usd}` : '';
            
            html += `
                <div class="suggestion-item" data-index="${index}">
                    ${imageHtml}
                    <div class="suggestion-content">
                        <div class="suggestion-name">${card.name}</div>
                        <div class="suggestion-details">
                            <span class="suggestion-set">${card.set}</span>
                            <span class="suggestion-rarity ${rarityClass}">${card.rarity}</span>
                            ${card.collector_number ? `<span>#${card.collector_number}</span>` : ''}
                        </div>
                    </div>
                    ${price ? `<div class="suggestion-price">${price}</div>` : ''}
                </div>
            `;
        });
        
        suggestionsContainer.innerHTML = html;
        suggestionsContainer.classList.add('show');
        
        // Add click listeners to suggestion items
        suggestionsContainer.querySelectorAll('.suggestion-item').forEach((item, index) => {
            item.addEventListener('click', () => selectSuggestion(index));
        });
    }
    
    function selectSuggestion(index) {
        if (index < 0 || index >= suggestions.length) return;
        
        const card = suggestions[index];
        
        // Fill form fields with card data
        fillCardForm(card);
        
        // Hide suggestions
        hideSuggestions();
        
        // Clear highlight
        currentHighlight = -1;
    }
    
    function fillCardForm(card) {
        // Fill basic fields
        cardNameInput.value = card.name;
        
        const setNameInput = document.getElementById('set_name');
        const setCodeInput = document.getElementById('set_code');
        const collectorNumberInput = document.getElementById('collector_number');
        const purchasePriceInput = document.getElementById('purchase_price');
        
        if (setNameInput) setNameInput.value = card.set_name || '';
        if (setCodeInput) setCodeInput.value = card.set || '';
        if (collectorNumberInput) collectorNumberInput.value = card.collector_number || '';
        
        // Set purchase price to current market price if available
        if (purchasePriceInput && card.prices.usd) {
            purchasePriceInput.value = card.prices.usd;
        }
        
        // Add visual feedback
        cardNameInput.classList.add('is-valid');
        setTimeout(() => {
            cardNameInput.classList.remove('is-valid');
        }, 2000);
    }
    
    function highlightSuggestion(index) {
        const items = suggestionsContainer.querySelectorAll('.suggestion-item');
        
        // Remove previous highlight
        items.forEach(item => item.classList.remove('highlighted'));
        
        // Add new highlight
        if (index >= 0 && index < items.length) {
            items[index].classList.add('highlighted');
            
            // Scroll into view if necessary
            const container = suggestionsContainer;
            const item = items[index];
            const containerRect = container.getBoundingClientRect();
            const itemRect = item.getBoundingClientRect();
            
            if (itemRect.bottom > containerRect.bottom) {
                container.scrollTop += itemRect.bottom - containerRect.bottom;
            } else if (itemRect.top < containerRect.top) {
                container.scrollTop += itemRect.top - containerRect.top;
            }
        }
    }
    
    function showLoading() {
        if (loadingSpinner) {
            loadingSpinner.style.display = 'block';
        }
    }
    
    function hideLoading() {
        if (loadingSpinner) {
            loadingSpinner.style.display = 'none';
        }
    }
    
    function hideSuggestions() {
        suggestionsContainer.classList.remove('show');
        currentHighlight = -1;
    }
    
    // Event listeners
    cardNameInput.addEventListener('input', function() {
        const query = this.value.trim();
        
        // Clear existing timeout
        clearTimeout(searchTimeout);
        
        // Set new timeout (300ms debounce)
        searchTimeout = setTimeout(() => {
            searchCards(query);
        }, 300);
    });
    
    cardNameInput.addEventListener('keydown', function(e) {
        const isVisible = suggestionsContainer.classList.contains('show');
        
        if (!isVisible || suggestions.length === 0) return;
        
        switch (e.key) {
            case 'ArrowDown':
                e.preventDefault();
                currentHighlight = Math.min(currentHighlight + 1, suggestions.length - 1);
                highlightSuggestion(currentHighlight);
                break;
                
            case 'ArrowUp':
                e.preventDefault();
                currentHighlight = Math.max(currentHighlight - 1, 0);
                highlightSuggestion(currentHighlight);
                break;
                
            case 'Enter':
                if (currentHighlight >= 0) {
                    e.preventDefault();
                    selectSuggestion(currentHighlight);
                }
                break;
                
            case 'Escape':
                hideSuggestions();
                break;
        }
    });
    
    cardNameInput.addEventListener('blur', function() {
        // Delay hiding to allow for click events
        setTimeout(() => {
            hideSuggestions();
        }, 200);
    });
    
    cardNameInput.addEventListener('focus', function() {
        if (this.value.length >= 2 && suggestions.length > 0) {
            suggestionsContainer.classList.add('show');
        }
    });
}