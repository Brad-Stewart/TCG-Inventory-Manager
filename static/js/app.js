// JavaScript for TCG Inventory Manager

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
        
        // Create a temporary message element
        const messageDiv = document.createElement('div');
        messageDiv.className = 'card-preview-large show';
        messageDiv.style.background = '#fff';
        messageDiv.style.padding = '20px';
        messageDiv.style.textAlign = 'center';
        messageDiv.style.color = '#666';
        messageDiv.innerHTML = `<i class="fas fa-image fa-2x mb-2"></i><br>No image available for<br><strong>${cardName}</strong>`;
        
        document.body.appendChild(messageDiv);
        backdrop.classList.add('show');
        
        // Clean up after mouse leave
        currentPreviewTimeout = setTimeout(() => {
            backdrop.classList.remove('show');
            document.body.removeChild(messageDiv);
        }, 2000);
    }
    
    function hideLargePreview() {
        clearTimeout(currentPreviewTimeout);
        
        currentPreviewTimeout = setTimeout(() => {
            backdrop.classList.remove('show');
            largePreview.classList.remove('show');
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