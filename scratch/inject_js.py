import re

js_code = """
        // ==========================================
        // DEPOSITS LOGIC
        // ==========================================
        let allDeposits = [];
        let filteredDeposits = null;
        let currentDepositsPage = 1;
        const DEPOSITS_PER_PAGE = 20;

        async function fetchDeposits() {
            try {
                const res = await fetch('/api/admin/store/deposits');
                const data = await res.json();
                allDeposits = data.deposits || [];
                filteredDeposits = null;
                currentDepositsPage = 1;
                renderDepositsList(allDeposits);
            } catch(e) { console.error("Error fetching deposits", e); }
        }

        function renderDepositsList(list) {
            const container = document.getElementById('deposits-list');
            const pagContainer = document.getElementById('deposits-pagination');

            if (!list || !list.length) {
                container.innerHTML = `
                <div style="text-align: center; padding: 40px 20px; background: var(--card-glass); border-radius: 16px; border: 1px dashed var(--border); margin-top: 0; backdrop-filter: blur(10px);">
                    <i class="fas fa-wallet" style="font-size: 2.5rem; color: var(--text-secondary); opacity: 0.3; margin-bottom: 12px;"></i>
                    <p style="color: var(--text-secondary); font-weight: 600; font-size: 0.95rem;">${translations[currentLang].no_data || 'No deposits found'}</p>
                </div>`;
                pagContainer.style.display = 'none';
                return;
            }

            const totalPages = Math.ceil(list.length / DEPOSITS_PER_PAGE);
            const start = (currentDepositsPage - 1) * DEPOSITS_PER_PAGE;
            const paged = list.slice(start, start + DEPOSITS_PER_PAGE);

            const rowS = "background: transparent; border: 1px solid var(--border); padding: 14px 18px; border-radius: 12px; display: flex; justify-content: space-between; align-items: center; gap: 15px;";
            const lblS = "color: var(--text-secondary); font-size: 0.8rem; font-weight: 700; text-transform: uppercase;";

            container.innerHTML = paged.map(item => `
                <div class="user-card" style="padding: 20px; margin-bottom: 15px; cursor: default;">
                    <div style="display: flex; flex-direction: column; gap: 10px;">
                        <div style="${rowS}">
                            <span style="${lblS}">${currentLang === 'ar' ? 'المستخدم' : 'User'}</span>
                            <div style="text-align: right;">
                                <div style="color: var(--text-primary); font-weight: 700; font-size: 0.95rem;">${item.user_name}</div>
                                <div style="color: var(--text-secondary); font-size: 0.8rem;">${item.user_handle} (${item.user_id})</div>
                            </div>
                        </div>
                        <div style="${rowS}">
                            <span style="${lblS}">${currentLang === 'ar' ? 'المبلغ' : 'Amount'}</span>
                            <span style="color: var(--success); font-weight: 800; font-size: 1.1rem;">$${Number(item.amount).toFixed(2)}</span>
                        </div>
                        <div style="${rowS}">
                            <span style="${lblS}">${currentLang === 'ar' ? 'الطريقة' : 'Method'}</span>
                            <span style="color: #3b82f6; font-weight: 700; font-size: 0.95rem;">${item.method}</span>
                        </div>
                        <div style="${rowS}">
                            <span style="${lblS}">${currentLang === 'ar' ? 'رقم العملية' : 'TxID'}</span>
                            <span style="color: var(--text-primary); font-weight: 700; font-size: 0.85rem; word-break: break-all;">${item.txid}</span>
                        </div>
                        <div style="${rowS}">
                            <span style="${lblS}">${currentLang === 'ar' ? 'التاريخ' : 'Date'}</span>
                            <span style="color: var(--text-secondary); font-weight: 600; font-size: 0.85rem; direction: ltr;">${formatDateTime(item.date)}</span>
                        </div>
                    </div>
                </div>
            `).join('');

            pagContainer.style.display = totalPages > 1 ? 'flex' : 'none';
            document.getElementById('pgInfoDeposits').innerText = `Page ${currentDepositsPage} / ${totalPages}`;
            document.getElementById('pgPrevDeposits').disabled = currentDepositsPage === 1;
            document.getElementById('pgNextDeposits').disabled = currentDepositsPage === totalPages;
        }

        function prevDepositsPage() { if(currentDepositsPage > 1) { currentDepositsPage--; renderDepositsList(filteredDeposits || allDeposits); } }
        function nextDepositsPage() { const total = Math.ceil((filteredDeposits || allDeposits).length / DEPOSITS_PER_PAGE); if(currentDepositsPage < total) { currentDepositsPage++; renderDepositsList(filteredDeposits || allDeposits); } }

        function searchDeposits() {
            const q = document.getElementById('deposits-search').value.toLowerCase().trim();
            if (!q) { filteredDeposits = null; currentDepositsPage = 1; renderDepositsList(allDeposits); return; }
            filteredDeposits = allDeposits.filter(d => String(d.user_id).includes(q) || String(d.txid).toLowerCase().includes(q));
            currentDepositsPage = 1;
            renderDepositsList(filteredDeposits);
            document.getElementById('reset-deposits-search-container').style.display = 'block';
        }
        function resetDepositsSearch() {
            document.getElementById('deposits-search').value = '';
            document.getElementById('reset-deposits-search-container').style.display = 'none';
            filteredDeposits = null;
            currentDepositsPage = 1;
            renderDepositsList(allDeposits);
        }

        // ==========================================
        // STORE USER PRICES LOGIC
        // ==========================================
        let allStoreUserPrices = [];
        let filteredStoreUserPrices = null;
        let currentStoreUserPricesPage = 1;
        const SUP_PER_PAGE = 20;

        async function fetchStoreUserPrices() {
            try {
                const res = await fetch('/api/admin/store/user-prices');
                const data = await res.json();
                allStoreUserPrices = data.prices || [];
                filteredStoreUserPrices = null;
                currentStoreUserPricesPage = 1;
                renderStoreUserPricesList(allStoreUserPrices);
            } catch(e) { console.error("Error fetching store user prices", e); }
        }

        function renderStoreUserPricesList(list) {
            const container = document.getElementById('store-user-prices-list');
            const pagContainer = document.getElementById('store-user-prices-pagination');

            if (!list || !list.length) {
                container.innerHTML = `
                <div style="text-align: center; padding: 40px 20px; background: var(--card-glass); border-radius: 16px; border: 1px dashed var(--border); margin-top: 0; backdrop-filter: blur(10px);">
                    <i class="fas fa-user-tag" style="font-size: 2.5rem; color: var(--text-secondary); opacity: 0.3; margin-bottom: 12px;"></i>
                    <p style="color: var(--text-secondary); font-weight: 600; font-size: 0.95rem;">${translations[currentLang].no_data || 'No custom prices found'}</p>
                </div>`;
                pagContainer.style.display = 'none';
                return;
            }

            const totalPages = Math.ceil(list.length / SUP_PER_PAGE);
            const start = (currentStoreUserPricesPage - 1) * SUP_PER_PAGE;
            const paged = list.slice(start, start + SUP_PER_PAGE);

            const rowS = "background: transparent; border: 1px solid var(--border); padding: 14px 18px; border-radius: 12px; display: flex; justify-content: space-between; align-items: center; gap: 15px;";
            const lblS = "color: var(--text-secondary); font-size: 0.8rem; font-weight: 700; text-transform: uppercase;";

            container.innerHTML = paged.map(item => `
                <div class="user-card" style="padding: 20px; margin-bottom: 15px;">
                    <div style="display: flex; flex-direction: column; gap: 10px;">
                        <div style="${rowS}">
                            <span style="${lblS}">${currentLang === 'ar' ? 'المستخدم' : 'User'}</span>
                            <div style="text-align: right;">
                                <div style="color: var(--text-primary); font-weight: 700; font-size: 0.95rem;">${item.user_name}</div>
                                <div style="color: var(--text-secondary); font-size: 0.8rem;">${item.user_handle} (${item.user_id})</div>
                            </div>
                        </div>
                        <div style="${rowS}">
                            <span style="${lblS}">${currentLang === 'ar' ? 'الدولة' : 'Country'}</span>
                            <span style="color: #3b82f6; font-weight: 700; font-size: 0.95rem;">${item.country_name} (${item.country_code})</span>
                        </div>
                        <div style="${rowS}">
                            <span style="${lblS}">${currentLang === 'ar' ? 'سعر البيع' : 'Sell Price'}</span>
                            <span style="color: var(--success); font-weight: 800; font-size: 1.1rem;">$${Number(item.sell_price).toFixed(2)}</span>
                        </div>
                        
                        <div style="display: flex; gap: 10px; margin-top: 5px;">
                            <button onclick='editStoreUserPrice(${JSON.stringify(item).replace(/'/g, "&#39;")})' style="flex:1; padding:10px; background: rgba(59, 130, 246, 0.1); color: #3b82f6; border: none; border-radius: 10px; font-weight: 700; cursor: pointer;">
                                <i class="fas fa-pen"></i> Edit
                            </button>
                            <button onclick='deleteStoreUserPrice(${item.id})' style="flex:1; padding:10px; background: rgba(239, 68, 68, 0.1); color: var(--danger); border: none; border-radius: 10px; font-weight: 700; cursor: pointer;">
                                <i class="fas fa-trash"></i> Delete
                            </button>
                        </div>
                    </div>
                </div>
            `).join('');

            pagContainer.style.display = totalPages > 1 ? 'flex' : 'none';
            document.getElementById('pgInfoStoreUserPrices').innerText = `Page ${currentStoreUserPricesPage} / ${totalPages}`;
            document.getElementById('pgPrevStoreUserPrices').disabled = currentStoreUserPricesPage === 1;
            document.getElementById('pgNextStoreUserPrices').disabled = currentStoreUserPricesPage === totalPages;
        }

        function prevStoreUserPricesPage() { if(currentStoreUserPricesPage > 1) { currentStoreUserPricesPage--; renderStoreUserPricesList(filteredStoreUserPrices || allStoreUserPrices); } }
        function nextStoreUserPricesPage() { const total = Math.ceil((filteredStoreUserPrices || allStoreUserPrices).length / SUP_PER_PAGE); if(currentStoreUserPricesPage < total) { currentStoreUserPricesPage++; renderStoreUserPricesList(filteredStoreUserPrices || allStoreUserPrices); } }

        function searchStoreUserPrices() {
            const q = document.getElementById('store-user-prices-search').value.toLowerCase().trim();
            if (!q) { filteredStoreUserPrices = null; currentStoreUserPricesPage = 1; renderStoreUserPricesList(allStoreUserPrices); return; }
            filteredStoreUserPrices = allStoreUserPrices.filter(u => String(u.user_id).includes(q) || String(u.country_name).toLowerCase().includes(q) || String(u.country_code).includes(q));
            currentStoreUserPricesPage = 1;
            renderStoreUserPricesList(filteredStoreUserPrices);
            document.getElementById('reset-store-user-prices-search-container').style.display = 'block';
        }
        function resetStoreUserPricesSearch() {
            document.getElementById('store-user-prices-search').value = '';
            document.getElementById('reset-store-user-prices-search-container').style.display = 'none';
            filteredStoreUserPrices = null;
            currentStoreUserPricesPage = 1;
            renderStoreUserPricesList(allStoreUserPrices);
        }

        // Store User Price Modal CRUD
        function showStoreUserPriceModal() {
            document.getElementById('m-sup-id').value = '';
            document.getElementById('m-sup-user-id').value = '';
            document.getElementById('m-sup-code').value = '';
            document.getElementById('m-sup-iso').value = 'XX';
            document.getElementById('m-sup-sell-price').value = '';
            document.getElementById('store-user-price-modal').classList.add('active');
        }
        function closeStoreUserPriceModal(e) {
            if (e && e.target !== e.currentTarget) return;
            document.getElementById('store-user-price-modal').classList.remove('active');
        }
        function onSupCountryCodeInput() {
            let cc = document.getElementById('m-sup-code').value.trim();
            if (cc.startsWith('+')) cc = cc.substring(1);
            if (countriesData && countriesData[cc]) {
                document.getElementById('m-sup-iso').value = countriesData[cc].iso || 'XX';
            }
        }
        function editStoreUserPrice(item) {
            document.getElementById('m-sup-id').value = item.id;
            document.getElementById('m-sup-user-id').value = item.user_id;
            document.getElementById('m-sup-code').value = item.country_code;
            document.getElementById('m-sup-iso').value = item.iso_code || 'XX';
            document.getElementById('m-sup-sell-price').value = item.sell_price;
            document.getElementById('store-user-price-modal').classList.add('active');
        }
        async function saveStoreUserPrice() {
            const btn = document.querySelector('#store-user-price-modal .btn-save');
            const uid = document.getElementById('m-sup-user-id').value.trim();
            const cc = document.getElementById('m-sup-code').value.trim();
            const iso = document.getElementById('m-sup-iso').value.trim();
            const sp = document.getElementById('m-sup-sell-price').value.trim();
            
            if (!uid || !cc || !sp) {
                tg.showAlert("Please fill User ID, Country Code, and Sell Price.");
                return;
            }

            btn.disabled = true;
            const originalHtml = btn.innerHTML;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';

            try {
                const res = await fetch('/api/admin/store/user-prices', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        id: document.getElementById('m-sup-id').value ? parseInt(document.getElementById('m-sup-id').value) : null,
                        user_id: parseInt(uid),
                        country_code: cc,
                        iso_code: iso || 'XX',
                        sell_price: parseFloat(sp)
                    })
                });
                if (res.ok) {
                    closeStoreUserPriceModal();
                    await fetchStoreUserPrices();
                } else {
                    const data = await res.json();
                    tg.showAlert(data.detail || data.message || "Failed to save");
                }
            } catch(e) { console.error(e); tg.showAlert("Error saving"); }
            btn.disabled = false;
            btn.innerHTML = originalHtml;
        }

        function deleteStoreUserPrice(id) {
            showConfirm(
                currentLang === 'ar' ? 'حذف السعر' : 'Delete Price',
                currentLang === 'ar' ? 'هل أنت متأكد من حذف هذا السعر المخصص؟' : 'Are you sure you want to delete this custom price?',
                async () => {
                    try {
                        const res = await fetch(`/api/admin/store/user-prices/${id}`, { method: 'DELETE' });
                        if (res.ok) {
                            fetchStoreUserPrices();
                        } else {
                            tg.showAlert("Failed to delete.");
                        }
                    } catch(e) { console.error(e); tg.showAlert("Error deleting."); }
                }
            );
        }
"""

with open('templates/admin_store.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Make sure we don't inject multiple times
if "DEPOSITS LOGIC" not in content:
    # Inject right before `const savedView = sessionStorage.getItem('last_view_admin_store') || 'home';`
    target = "        const savedView = sessionStorage.getItem('last_view_admin_store') || 'home';"
    new_content = content.replace(target, js_code + "\n" + target)

    # We also need to add them to `switchNav` function
    switchNav_target = """            if (id === 'settings') fetchStoreSettings();"""
    switchNav_replacement = """            if (id === 'settings') fetchStoreSettings();
            if (id === 'deposits') fetchDeposits();
            if (id === 'store-user-prices') fetchStoreUserPrices();"""
    new_content = new_content.replace(switchNav_target, switchNav_replacement)

    with open('templates/admin_store.html', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("JS injected successfully.")
else:
    print("JS already injected.")
