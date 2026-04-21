
        const tg = window.Telegram.WebApp;
        tg.expand();

        // ─── Native Theme Support ───
        function applyTheme() {
            const scheme = tg.colorScheme;
            document.body.className = scheme === 'light' ? 'light-mode' : 'dark-mode';
            tg.headerColor = scheme === 'light' ? '#ffffff' : '#111113';
            tg.backgroundColor = scheme === 'light' ? '#ffffff' : '#111113';
        }
        tg.onEvent('themeChanged', applyTheme);
        applyTheme();

        const translations = {
            en: {
                nav_dashboard: "Dashboard",
                nav_prices: "Buying Prices",
                nav_users: "Customers",
                nav_close: "Close",
                stat_section: "Inventory",
                stat_total: "TOTAL ACCOUNTS",
                stat_pending: "PENDING APPROVAL",
                total_balance: "TOTAL BALANCE",
                recent_ops: "Recent Operations",
                buying_prices: "Buying Prices",
                btn_add: "Add",
                btn_save: "Add Country",
                btn_reset: "Reset",
                modal_title: "Add New Country",
                lbl_code: "Code",
                lbl_buy: "Price",
                lbl_delay: "Approval Delay",
                no_ops: "No accounts found",
                no_users: "No users found",
                no_countries: "No countries found",
                buy_lbl: "Buying Price",
                stat_total_users: "TOTAL USERS",
                stat_banned: "BANNED USERS",
                unit_users: "USERS",
                btn_find: "Find",
                search_placeholder: "Search users...",
                user_mgmt: "User Management",
                tab_active: "Active",
                tab_banned: "Banned",
                nav_history: "Accounts History",
                pg_next: "Next",
                stat_pending_ops: "PENDING ACCOUNTS",
                stat_total_ops: "TOTAL ACCOUNTS",
                stat_accepted_ops: "ACCEPTED ACCOUNTS",
                unit_ops: "ACCOUNTS",
                unit_accs: "ACCOUNTS",
                lbl_status: "Status",
                lbl_user: "User ID",
                lbl_number: "Number",
                lbl_country: "Country",
                lbl_price: "Price",
                lbl_date: "Date",
                st_pending: "PENDING",
                st_accepted: "ACCEPTED",
                st_rejected: "REJECTED",
                time_processing: "Processing...",
                nav_settings: "Settings",
                pg_prev: "Prev",
                pg_next: "Next",
                stat_active: "Active Users",
                stat_active_countries: "Active Countries",
                stat_inactive_countries: "Inactive Countries",
                tab_inactive: "Inactive",
                lbl_bot_name: "Bot Name",
                btn_save_settings: "Save Settings",
                stat_total_countries: "TOTAL COUNTRIES",
                search_countries_ph: "Search countries...",
                btn_confirm: "Delete Now",
                btn_cancel: "Cancel",
                lbl_full_name: "Full Name",
                btn_ban_user: "Ban User",
                btn_unban_user: "Unban User",
                lbl_pending_balance: "Pending Balance",
                ph_amount: "Amount..."
            },
            ar: {
                nav_dashboard: "الرئيسية",
                nav_prices: "أسعار الشراء",
                nav_users: "العملاء",
                nav_close: "إغلاق",
                stat_section: "المخزون",
                stat_total: "إجمالي الحسابات",
                stat_pending: "بانتظار الموافقة",
                total_balance: "إجمالي الأرصدة",
                recent_ops: "أحدث العمليات",
                buying_prices: "أسعار الشراء",
                btn_add: "إضافة",
                btn_save: "إضافة دولة",
                btn_reset: "إعادة ضبط",
                modal_title: "إضافة دولة جديدة",
                lbl_code: "كود",
                lbl_buy: "السعر",
                lbl_delay: "تأخير الموافقة",
                no_ops: "لا توجد عمليات",
                st_pending: "قيد المراجعة",
                st_accepted: "تم القبول",
                st_rejected: "تم الرفض",
                time_processing: "جاري المعالجة...",
                no_users: "لا يوجد مستخدمين",
                no_countries: "لم يتم العثور على دول",
                buy_lbl: "سعر الشراء",
                stat_total_users: "إجمالي المستخدمين",
                stat_banned: "المحظورين",
                unit_users: "مستخدم",
                btn_find: "بحث",
                search_placeholder: "بحث عن مستخدم...",
                user_mgmt: "إدارة المستخدمين",
                tab_active: "نشط",
                tab_banned: "محظور",
                pg_next: "التالي",
                pg_prev: "السابق",
                nav_history: "سجل العمليات",
                stat_pending_ops: "عمليات قيد الانتظار",
                stat_total_ops: "إجمالي العمليات",
                stat_accepted_ops: "الحسابات المقبولة",
                stat_rejected_ops: "الحسابات المرفوضة",
                unit_ops: "عملية",
                unit_accs: "حساب",
                no_countries: "لا توجد دول مضافة",
                buy_lbl: "سعر الشراء",
                stat_total_users: "إجمالي المستخدمين",
                stat_banned: "المحظورين",
                unit_users: "مستخدم",
                btn_find: "بحث",
                search_placeholder: "بحث عن مستخدم...",
                user_mgmt: "إدارة المستخدمين",
                tab_active: "نشط",
                tab_inactive: "غير نشط",
                tab_banned: "محظور",
                nav_history: "سجل العمليات",
                stat_total_ops: "إجمالي العمليات",
                stat_accepted_ops: "الأرقام المقبولة",
                stat_rejected_ops: "الأرقام المرفوضة",
                unit_ops: "عملية",
                unit_accs: "رقم",
                lbl_status: "الحالة",
                lbl_user: "معرّف المستخدم",
                lbl_number: "الرقم",
                lbl_country: "الدولة",
                lbl_price: "السعر",
                lbl_date: "التاريخ",
                nav_settings: "الإعدادات",
                pg_prev: "السابق",
                pg_next: "التالي",
                stat_active: "المستخدمون النشطون",
                stat_active_countries: "الدول النشطة",
                stat_inactive_countries: "الدول غير النشطة",
                lbl_bot_name: "اسم البوت",
                btn_save_settings: "حفظ الإعدادات",
                stat_total_countries: "إجمالي الدول",
                search_countries_ph: "بحث عن دولة...",
                confirm_title: "هل أنت متأكد؟",
                confirm_delete_msg: "لا يمكن التراجع عن هذا الإجراء بعد تنفيذه.",
                btn_confirm: "حذف الآن",
                btn_cancel: "إلغاء",
                lbl_full_name: "الاسم الكامل",
                lbl_current_balance: "الرصيد الحالي",
                btn_edit_balance: "تعديل الرصيد",
                btn_ban_user: "حظر المستخدم",
                btn_unban_user: "إلغاء حظر المستخدم",
                lbl_pending_balance: "الرصيد المعلق",
                ph_amount: "المبلغ..."
            }
        };

        let currentLang = localStorage.getItem('admin_lang') || 'en';
        let allUsers = [];
        let currentTab = 'active';
        let filteredUsers = null;
        const USERS_PER_PAGE = 5;
        let currentPage = 1;
        let allPrices = [];
        let filteredPrices = null;
        const PRICES_PER_PAGE = 10;
        let currentPricePage = 1;
        let currentPriceTab = 'active';

        function updateUI() {
            document.documentElement.lang = currentLang;
            document.documentElement.dir = currentLang === 'ar' ? 'rtl' : 'ltr';
            document.querySelectorAll('[data-i18n]').forEach(el => {
                const key = el.getAttribute('data-i18n');
                if (translations[currentLang][key]) el.innerText = translations[currentLang][key];
            });
            document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
                const key = el.getAttribute('data-i18n-placeholder');
                if (translations[currentLang][key]) el.placeholder = translations[currentLang][key];
            });
        }

        function toggleLanguage() {
            currentLang = currentLang === 'en' ? 'ar' : 'en';
            localStorage.setItem('admin_lang', currentLang);
            updateUI();
        }

        function openNav() {
            document.getElementById('navSidebar').classList.add('open');
            document.getElementById('navOverlay').classList.add('show');
        }
        function closeNav() {
            document.getElementById('navSidebar').classList.remove('open');
            document.getElementById('navOverlay').classList.remove('show');
        }

        function switchNav(id, btn, skipToggle = false) {
            if (!skipToggle) closeNav();
            // Hide all first
            document.querySelectorAll('.view-section').forEach(s => s.classList.remove('active'));

            const scroller = document.getElementById('app-content-scroller');
            if (scroller) scroller.scrollTop = 0;

            document.getElementById('section-' + id).classList.add('active');
            document.querySelectorAll('.nav-item').forEach(m => m.classList.remove('active'));
            if (btn) btn.classList.add('active');

            sessionStorage.setItem('last_view_admin_sourcing', id);
            if (!skipToggle) closeNav();

            // Update page title
            const titleMap = { home: 'nav_dashboard', prices: 'nav_prices', users: 'nav_users', history: 'nav_history', settings: 'nav_settings' };
            const titleEl = document.getElementById('page-title');
            titleEl.setAttribute('data-i18n', titleMap[id]);
            titleEl.innerText = translations[currentLang][titleMap[id]];
        }

        async function init() {
            try {
                const res = await fetch('/api/admin/sourcing/data');
                const data = await res.json();
                document.getElementById('stat-total-sourced').innerText = data.stats.total_sourced;
                if (data.bot_name) document.getElementById('sideBrandName').textContent = data.bot_name;
                const uname = tg.initDataUnsafe?.user?.first_name || "AD";
                const uIEl = document.getElementById('userInitial');
                if (uIEl) uIEl.textContent = uname.charAt(0).toUpperCase();
                document.getElementById('stat-pending').innerText = data.stats.pending_count;
                document.getElementById('stat-total-balance').innerText = `$${Number(data.stats.total_balance).toFixed(2)}`;

                // History Stats
                document.getElementById('stat-history-pending').innerText = data.stats.pending_count;
                document.getElementById('stat-history-accepted').innerText = data.stats.accepted_sourced;
                document.getElementById('stat-history-rejected').innerText = data.stats.rejected_sourced;

                renderRecent(data.recent);
                fetchAdminHistory(currentAdminHistoryPage);
                allPrices = data.prices || [];

                // Update counts
                document.getElementById('stat-active-countries').innerText = allPrices.length;

                renderPrices(allPrices);

                allUsers = (data.users || []).reverse();
                document.getElementById('user-count').innerText = data.stats.user_count || allUsers.length;
                document.getElementById('banned-count').innerText = allUsers.filter(u => u.banned).length;
                renderUsers(filteredUsers || allUsers);
            } catch (e) { console.error(e); }
            finally { document.getElementById('loader').style.display = 'none'; }
        }

        function switchTab(tab, btn) {
            currentTab = tab;
            currentPage = 1;
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            renderUsers(filteredUsers || allUsers);
        }

        function searchUsers() {
            const q = document.getElementById('user-search').value.trim().toLowerCase();
            if (!q) { filteredUsers = null; renderUsers(allUsers); return; }
            filteredUsers = allUsers.filter(u => String(u.id).includes(q));
            currentPage = 1;
            document.getElementById('reset-search-container').style.display = 'block';
            renderUsers(filteredUsers);
        }

        function resetSearch() {
            document.getElementById('user-search').value = '';
            filteredUsers = null;
            currentPage = 1;
            document.getElementById('reset-search-container').style.display = 'none';
            renderUsers(allUsers);
        }

        function renderUsers(list) {
            const container = document.getElementById('user-list');
            const filtered = currentTab === 'banned' ? list.filter(u => u.banned) : list.filter(u => !u.banned);

            if (!filtered.length) {
                container.innerHTML = `
                <div style="text-align: center; padding: 40px 20px; background: var(--card-glass); border-radius: 16px; border: 1px dashed var(--border); margin-top: 10px; backdrop-filter: blur(10px);">
                    <i class="fas fa-users-slash" style="font-size: 2.5rem; color: var(--text-secondary); opacity: 0.3; margin-bottom: 12px;"></i>
                    <p style="color: var(--text-secondary); font-weight: 600; font-size: 0.95rem;">${translations[currentLang].no_users}</p>
                </div>`;
                document.getElementById('user-pagination').style.display = 'none';
                return;
            }

            // Pagination
            const totalPages = Math.ceil(filtered.length / USERS_PER_PAGE);
            const start = (currentPage - 1) * USERS_PER_PAGE;
            const paged = filtered.slice(start, start + USERS_PER_PAGE);

            container.innerHTML = paged.map((u, i) => {
                const idx = start + i + 1;
                const statusColor = u.banned ? 'var(--error)' : 'var(--success)';
                const statusIcon = u.banned ? '<i class="fas fa-times" style="font-size: 0.9rem;"></i>' : '<i class="fas fa-check" style="font-size: 0.9rem;"></i>';
                const statusText = u.banned
                    ? (currentLang === 'ar' ? 'محظور' : 'BANNED')
                    : (currentLang === 'ar' ? 'نشط' : 'ACTIVE');
                return `
                <div class="user-card" onclick='openManageModal(${JSON.stringify(u)})'>
                    <div style="display: flex; flex-direction: column; gap: 10px;">
                        <!-- Account Status -->
                        <div style="background: var(--bg-elevated); border: 1px solid var(--border); padding: 14px 18px; border-radius: 12px; display: flex; justify-content: space-between; align-items: center;">
                            <span style="color: var(--text-secondary); font-size: 0.8rem; font-weight: 700; text-transform: uppercase;">${currentLang === 'ar' ? 'الحالة' : 'Status'}</span>
                            <span style="color: ${statusColor}; font-weight: 900; font-size: 0.9rem; display: flex; align-items: center; gap: 8px; letter-spacing: 0.5px;">
                                ${statusIcon} ${statusText}
                            </span>
                        </div>
                        <!-- Name -->
                        <div style="background: var(--bg-elevated); border: 1px solid var(--border); padding: 14px 18px; border-radius: 12px; display: flex; justify-content: space-between; align-items: flex-start; gap: 20px;">
                            <span style="color: var(--text-secondary); font-size: 0.8rem; font-weight: 700; text-transform: uppercase; flex-shrink: 0;">${currentLang === 'ar' ? 'الاسم' : 'Name'}</span>
                            <span style="color: #00d2ff; font-weight: 700; font-size: 1rem; text-align: right; word-break: break-word;">${u.full_name || 'N/A'}</span>
                        </div>
                        <!-- Username -->
                        <div style="background: var(--bg-elevated); border: 1px solid var(--border); padding: 14px 18px; border-radius: 12px; display: flex; justify-content: space-between; align-items: flex-start; gap: 20px;">
                            <span style="color: var(--text-secondary); font-size: 0.8rem; font-weight: 700; text-transform: uppercase; flex-shrink: 0;">${currentLang === 'ar' ? 'المعرف' : 'Username'}</span>
                            <span style="color: #bf5af2; font-weight: 700; font-size: 1rem; text-align: right; word-break: break-all;">${u.username ? (u.username.startsWith('@') ? u.username : '@' + u.username) : 'N/A'}</span>
                        </div>
                        <!-- User ID -->
                        <div style="background: var(--bg-elevated); border: 1px solid var(--border); padding: 14px 18px; border-radius: 12px; display: flex; justify-content: space-between; align-items: center;">
                            <span style="color: var(--text-secondary); font-size: 0.8rem; font-weight: 700; text-transform: uppercase;">${currentLang === 'ar' ? 'رقم المعرف' : 'User ID'}</span>
                            <span style="color: #ff9f0a; font-weight: 800; font-size: 1rem;">${u.id}</span>
                        </div>
                        <!-- Balance -->
                        <div style="background: var(--bg-elevated); border: 1px solid var(--border); padding: 14px 18px; border-radius: 12px; display: flex; justify-content: space-between; align-items: center;">
                            <span style="color: var(--text-secondary); font-size: 0.8rem; font-weight: 700; text-transform: uppercase;">${currentLang === 'ar' ? 'الرصيد' : 'Balance'}</span>
                            <span style="color: #30d158; font-weight: 900; font-size: 1.1rem;">$${Number(u.balance_sourcing).toFixed(2)}</span>
                        </div>
                        <!-- Pending Balance -->
                        <div style="background: var(--bg-elevated); border: 1px solid var(--border); padding: 14px 18px; border-radius: 12px; display: flex; justify-content: space-between; align-items: center;">
                            <span style="color: var(--text-secondary); font-size: 0.8rem; font-weight: 700; text-transform: uppercase;">${currentLang === 'ar' ? 'الرصيد المعلق' : 'Pending Balance'}</span>
                            <span style="color: #ff9f0a; font-weight: 800; font-size: 1rem;">$${Number(u.pending_balance || 0).toFixed(2)}</span>
                        </div>
                        <!-- Sold Count -->
                        <div style="background: var(--bg-elevated); border: 1px solid var(--border); padding: 14px 18px; border-radius: 12px; display: flex; justify-content: space-between; align-items: center;">
                            <span style="color: var(--text-secondary); font-size: 0.8rem; font-weight: 700; text-transform: uppercase;">${currentLang === 'ar' ? 'أرقام باعها' : 'Numbers Sold'}</span>
                            <span style="color: #ffcc00; font-weight: 800; font-size: 1rem;">${u.sold_count}</span>
                        </div>
                        <!-- Accepted Count -->
                        <div style="background: var(--bg-elevated); border: 1px solid var(--border); padding: 14px 18px; border-radius: 12px; display: flex; justify-content: space-between; align-items: center;">
                            <span style="color: var(--text-secondary); font-size: 0.8rem; font-weight: 700; text-transform: uppercase;">${currentLang === 'ar' ? 'أرقام مقبولة' : 'Accepted'}</span>
                            <span style="color: #5eeb8b; font-weight: 800; font-size: 1rem;">${u.accepted_count}</span>
                        </div>
                    </div>
                </div>`;
            }).join('');

            // pagination controls
            const pagContainer = document.getElementById('user-pagination');
            if (totalPages > 1) {
                pagContainer.style.display = 'flex';
                document.getElementById('page-info').innerText = `Page ${currentPage} of ${totalPages}`;
                const prevBtn = pagContainer.querySelector('button[onclick="prevPage()"]');
                const nextBtn = pagContainer.querySelector('button[onclick="nextPage()"]');
                prevBtn.disabled = (currentPage === 1);
                nextBtn.disabled = (currentPage === totalPages);
            } else {
                pagContainer.style.display = 'none';
            }
        }

        function prevPage() {
            if (currentPage > 1) {
                currentPage--;
                renderUsers(filteredUsers || allUsers);
                document.getElementById('user-mgmt-section').scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        }
        function nextPage() {
            const list = filteredUsers || allUsers;
            const filtered = currentTab === 'banned' ? list.filter(u => u.banned) : list.filter(u => !u.banned);
            const totalPages = Math.ceil(filtered.length / USERS_PER_PAGE);
            if (currentPage < totalPages) {
                currentPage++;
                renderUsers(list);
                document.getElementById('user-mgmt-section').scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        }

        let currentUser = null;
        function openManageModal(u) {
            currentUser = u;
            document.getElementById('manage-name').innerText = (u.full_name || u.id).toUpperCase();
            const displayId = (u.username || 'N/A').toString();
            document.getElementById('manage-id').innerText = displayId.startsWith('@') ? displayId : '@' + displayId;
            document.getElementById('manage-balance').innerText = `$${Number(u.balance_sourcing).toFixed(2)}`;
            document.getElementById('adjust-amount').value = '';

            const banBtn = document.getElementById('manage-ban-btn');
            if (u.banned) {
                banBtn.innerText = translations[currentLang].btn_unban_user;
                banBtn.className = 'manage-btn success';
            } else {
                banBtn.innerText = translations[currentLang].btn_ban_user;
                banBtn.className = 'manage-btn danger';
            }

            document.getElementById('user-manage-modal').classList.add('active');
        }

        async function syncUserIdentity() {
            if (!currentUser) return;
            const btn = document.querySelector('.sync-btn');
            if (btn) btn.style.transform = 'rotate(360deg)';

            try {
                const res = await fetch('/api/admin/user/sync', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ user_id: currentUser.id, bot_type: "sourcing" })
                });
                const data = await res.json();
                if (data.status === 'success') {
                    currentUser.full_name = data.full_name;
                    currentUser.username = data.username.startsWith('@') ? data.username.substring(1) : data.username;
                    document.getElementById('manage-name').innerText = data.full_name.toUpperCase();

                    const dispId = (data.username || currentUser.id).toString();
                    document.getElementById('manage-id').innerText = dispId.startsWith('@') ? dispId : '@' + dispId;
                    init();
                }
            } catch (e) { console.error(e); }
            finally { if (btn) btn.style.transform = 'rotate(0deg)'; }
        }

        async function adjustBalanceInline(type) {
            if (!currentUser) return;
            const input = document.getElementById('adjust-amount');
            const val = parseFloat(input.value);
            if (isNaN(val) || val <= 0) return;

            const adjustment = type === 'plus' ? val : -val;
            const newBalance = parseFloat(currentUser.balance_sourcing) + adjustment;

            const res = await fetch('/api/admin/user/balance', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: currentUser.id, amount: newBalance, type: 'sourcing' })
            });

            if (res.ok) {
                currentUser.balance_sourcing = newBalance;
                document.getElementById('manage-balance').innerText = `$${newBalance.toFixed(2)}`;
                input.value = '';
                init(); // Refresh data in background
            }
        }

        function closeManageModal() {
            document.getElementById('user-manage-modal').classList.remove('active');
            currentUser = null;
        }



        async function manageBan() {
            if (!currentUser) return;
            const currentStatus = currentUser.banned;
            const res = await fetch('/api/admin/user/toggle-ban', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: currentUser.id, bot_type: 'sourcing', banned: !currentStatus })
            });
            if (res.ok) {
                currentUser.banned = !currentStatus;
                openManageModal(currentUser); // Refresh UI
                init();
            }
        }

        async function promptBalance(userId, currentBalance, type) {
            const amount = prompt(currentLang === 'ar' ? `أدخل الرصيد الجديد للمستخدم ${userId}:` : `Enter new balance for user ${userId}:`, currentBalance);
            if (amount === null) return;
            const val = parseFloat(amount);
            if (isNaN(val)) return;

            try {
                const res = await fetch('/api/admin/user/balance', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ user_id: userId, amount: val, type: type })
                });
                if (res.ok) init();
                else alert('Failed to update balance');
            } catch (e) { console.error(e); }
        }

        async function toggleBan(userId, currentStatus, botType) {
            const confirmed = await showConfirm();
            if (!confirmed) return;

            try {
                const res = await fetch('/api/admin/user/toggle-ban', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ user_id: userId, bot_type: botType, banned: !currentStatus })
                });
                if (res.ok) init();
                else alert('Failed to toggle ban');
            } catch (e) { console.error(e); }
        }

        let currentAdminHistoryPage = 1;
        let totalAdminHistoryPages = 1;
        const ADMIN_HISTORY_LIMIT = 1; // User requested 1 for testing

        async function fetchAdminHistory(page) {
            try {
                const res = await fetch(`/api/admin/sourcing/history?page=${page}&limit=${ADMIN_HISTORY_LIMIT}`);
                const data = await res.json();

                totalAdminHistoryPages = data.total_pages;
                currentAdminHistoryPage = data.current_page;

                renderHistory(data.history);
                updateAdminHistoryPagination();
            } catch (e) { console.error("Admin History error:", e); }
        }

        function updateAdminHistoryPagination() {
            const pg = document.getElementById('history-pagination');
            pg.style.display = totalAdminHistoryPages > 1 ? 'flex' : 'none';
            document.getElementById('pgInfoAdminHist').innerText = `Page ${currentAdminHistoryPage} of ${totalAdminHistoryPages}`;
            document.getElementById('pgPrevAdminHist').disabled = (currentAdminHistoryPage <= 1);
            document.getElementById('pgNextAdminHist').disabled = (currentAdminHistoryPage >= totalAdminHistoryPages);
        }

        async function moveAdminHistoryPage(delta) {
            const nextP = currentAdminHistoryPage + delta;
            if (nextP >= 1 && nextP <= totalAdminHistoryPages) {
                await fetchAdminHistory(nextP);
                document.getElementById('history-section-card').scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        }

        function renderRecent(list) {
            const container = document.getElementById('recent-sourced');
            if (!list.length) {
                container.innerHTML = `
                <div style="text-align: center; padding: 40px 20px; background: rgba(0,0,0,0.15); border-radius: 16px; border: 1px dashed rgba(255,255,255,0.05); margin-top: 0;">
                    <i class="fas fa-history" style="font-size: 2.5rem; color: rgba(255,255,255,0.1); margin-bottom: 12px;"></i>
                    <p style="color: var(--text-secondary); font-weight: 600; font-size: 0.95rem;">${translations[currentLang].no_ops}</p>
                </div>`;
                return;
            }
            container.innerHTML = list.slice(0, 5).map(item => `
                <div class="list-item">
                    <div class="item-info">
                        <h4>${item.phone}</h4>
                        <p>${item.country} | <span style="color: var(--accent); font-weight: 700;">$${item.buy_price}</span></p>
                    </div>
                    <span class="badge ${item.status === 'AVAILABLE' ? 'badge-success' : 'badge-warning'}">${item.status}</span>
                </div>
            `).join('');
        }

        function searchPrices() {
            const q = document.getElementById('price-search').value.trim().toLowerCase();
            if (!q) { filteredPrices = null; currentPricePage = 1; renderPrices(allPrices); return; }
            filteredPrices = allPrices.filter(p => (p.name && p.name.toLowerCase().includes(q)) || String(p.code).includes(q));
            currentPricePage = 1;
            document.getElementById('reset-price-search-container').style.display = 'block';
            renderPrices(filteredPrices);
        }

        function resetPriceSearch() {
            document.getElementById('price-search').value = '';
            filteredPrices = null;
            currentPricePage = 1;
            document.getElementById('reset-price-search-container').style.display = 'none';
            renderPrices(allPrices);
        }

        function prevPricePage() {
            if (currentPricePage > 1) {
                currentPricePage--;
                renderPrices(filteredPrices || allPrices);
                document.getElementById('price-mgmt-section').scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        }

        function nextPricePage() {
            const list = filteredPrices || allPrices;
            const totalPages = Math.ceil(list.length / PRICES_PER_PAGE);
            if (currentPricePage < totalPages) {
                currentPricePage++;
                renderPrices(list);
                document.getElementById('price-mgmt-section').scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        }

        function switchPriceTab(tab, btn) {
            currentPriceTab = tab;
            document.querySelectorAll('#section-prices .tab-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentPricePage = 1;
            renderPrices(allPrices);
        }

        function renderPrices(list) {
            // Filter based on tab
            const filteredByTab = list.filter(p => {
                if (currentPriceTab === 'active') return p.buy_price > 0;
                return p.buy_price <= 0;
            });
            const container = document.getElementById('price-list');
            const pagContainer = document.getElementById('price-pagination');

            if (!list || !list.length) {
                container.innerHTML = `
                <div style="text-align: center; padding: 40px 20px; background: var(--card-glass); border-radius: 16px; border: 1px dashed var(--border); margin-top: 0; backdrop-filter: blur(10px);">
                    <i class="fas fa-tags" style="font-size: 2.5rem; color: var(--text-secondary); opacity: 0.15; margin-bottom: 12px;"></i>
                    <p style="color: var(--text-secondary); font-weight: 600; font-size: 0.95rem;">${translations[currentLang].no_countries}</p>
                </div>`;
                pagContainer.style.display = 'none';
                return;
            }

            const totalPages = Math.ceil(filteredByTab.length / PRICES_PER_PAGE);
            const start = (currentPricePage - 1) * PRICES_PER_PAGE;
            const paged = filteredByTab.slice(start, start + PRICES_PER_PAGE);

            container.innerHTML = paged.map((p, i) => {
                const idx = start + i + 1;
                return `
                <div class="user-card" style="position: relative; cursor: default;">
                    <div style="display: flex; flex-direction: column; gap: 10px; margin-bottom: 15px;">
                        <!-- Name -->
                        <div style="background: transparent; border: 1px solid var(--border); padding: 14px 18px; border-radius: 12px; display: flex; justify-content: space-between; align-items: flex-start; gap: 20px;">
                            <span style="color: var(--text-secondary); font-size: 0.8rem; font-weight: 700; text-transform: uppercase; flex-shrink: 0;">${currentLang === 'ar' ? 'الاسم' : 'Name'}</span>
                            <span style="color: var(--success); font-weight: 800; font-size: 1.1rem; text-align: right; word-break: break-all; flex: 1; min-width: 0;">${p.name.replace(/\s?\(?[A-Z]{2,3}\)?$/, '').trim()}</span>
                        </div>
                        <!-- Code -->
                        <div style="background: transparent; border: 1px solid var(--border); padding: 14px 18px; border-radius: 12px; display: flex; justify-content: space-between; align-items: center;">
                            <span style="color: var(--text-secondary); font-size: 0.8rem; font-weight: 700; text-transform: uppercase;">${currentLang === 'ar' ? 'كود' : 'Code'}</span>
                            <span style="color: var(--accent-purple); font-weight: 800; font-size: 1.1rem;">+${p.code}</span>
                        </div>
                        <!-- Price -->
                        <div style="background: transparent; border: 1px solid var(--border); padding: 14px 18px; border-radius: 12px; display: flex; justify-content: space-between; align-items: center;">
                            <span style="color: var(--text-secondary); font-size: 0.8rem; font-weight: 700; text-transform: uppercase;">${currentLang === 'ar' ? 'السعر' : 'Price'}</span>
                            <span style="color: var(--accent); font-weight: 900; font-size: 1.1rem;">$${Number(p.buy_price).toFixed(2)}</span>
                        </div>
                    </div>
                    <!-- Action Buttons -->
                    <div style="display: flex; gap: 10px;">
                        <button class="primary-btn" style="flex: 1; background: rgba(96, 165, 250, 0.1); color: var(--accent); border: 1px solid rgba(96, 165, 250, 0.2); box-shadow: none; padding: 14px; font-size: 0.95rem;" onclick="editPrice('${p.code}', '${p.iso}', ${p.buy_price}, ${p.approve_delay})">
                            <i class="fas fa-pen" style="margin-right: 5px;"></i> ${currentLang === 'ar' ? 'تعديل' : 'Edit'}
                        </button>
                        <button class="primary-btn" style="flex: 1; background: rgba(239, 68, 68, 0.1); color: var(--danger); border: 1px solid rgba(239, 68, 68, 0.2); box-shadow: none; padding: 14px; font-size: 0.95rem;" onclick="deletePrice('${p.code}', '${p.iso}')">
                            <i class="fas fa-trash" style="margin-right: 5px;"></i> ${currentLang === 'ar' ? 'حذف' : 'Delete'}
                        </button>
                    </div>
                </div>
                `;
            }).join('');

            if (totalPages > 1) {
                pagContainer.style.display = 'flex';
                document.getElementById('price-page-info').innerText = currentLang === 'ar' ? `صفحة ${currentPricePage} من ${totalPages}` : `Page ${currentPricePage} of ${totalPages}`;
                const prevBtn = pagContainer.querySelector('button[onclick="prevPricePage()"]');
                const nextBtn = pagContainer.querySelector('button[onclick="nextPricePage()"]');

                prevBtn.disabled = (currentPricePage === 1);
                nextBtn.disabled = (currentPricePage === totalPages);

                // Visual feedback for disabled buttons
                prevBtn.style.opacity = prevBtn.disabled ? '0.3' : '1';
                prevBtn.style.cursor = prevBtn.disabled ? 'not-allowed' : 'pointer';
                nextBtn.style.opacity = nextBtn.disabled ? '0.3' : '1';
                nextBtn.style.cursor = nextBtn.disabled ? 'not-allowed' : 'pointer';
            } else {
                pagContainer.style.display = 'none';
            }
        }

        function openPriceModal() {
            document.getElementById('m-code').value = '';
            document.getElementById('m-buy').value = '';
            document.getElementById('m-delay').value = '';
            document.getElementById('m-country-group').style.display = 'none';
            document.getElementById('m-country-container').innerHTML = '';
            document.getElementById('price-modal').classList.add('active');
        }

        async function editPrice(code, iso, buy, delay) {
            document.getElementById('m-code').value = code;
            document.getElementById('m-buy').value = buy;
            document.getElementById('m-delay').value = delay;
            
            await onCountryCodeInput();
            const box = document.getElementById('m-iso-box');
            if (box) box.value = iso;

            document.getElementById('price-modal').classList.add('active');
        }

        function closePriceModal(e) {
            if (e && e.target && e.target !== document.getElementById('price-modal')) return;
            document.getElementById('price-modal').classList.remove('active');
        }

        async function onCountryCodeInput() {
            const code = document.getElementById('m-code').value.trim().replace('+', '');
            const group = document.getElementById('m-country-group');
            const container = document.getElementById('m-country-container');
            
            if (code.length < 1) {
                group.style.display = 'none';
                return;
            }

            try {
                const res = await fetch(`/api/admin/countries-for-code/${code}`);
                const data = await res.json();
                
                if (data && data.length > 0) {
                    group.style.display = 'block';
                    if (data.length === 1) {
                        // Single country
                        container.innerHTML = `
                            <input type="text" id="m-iso-box" class="input-field" value="${data[0].flag} ${data[0].name}" readonly 
                                   data-iso="${data[0].iso}" data-name="${data[0].name}"
                                   style="background: var(--bg); opacity: 0.8; cursor: not-allowed;">
                        `;
                    } else {
                        // Multiple countries
                        container.innerHTML = `
                            <select id="m-iso-box" class="input-field" style="background: var(--bg); color: var(--text-p); border: 1px solid var(--border);">
                                ${data.map(c => `<option value="${c.iso}" data-name="${c.name}">${c.flag} ${c.name}</option>`).join('')}
                            </select>
                        `;
                    }
                } else {
                    group.style.display = 'none';
                }
            } catch (err) {
                group.style.display = 'none';
            }
        }

        async function savePriceChanges() {
            const code = document.getElementById('m-code').value.trim().replace('+', '');
            const isoBox = document.getElementById('m-iso-box');
            
            if (!code || !isoBox) return;

            let iso, name;
            if (isoBox.tagName === 'INPUT') {
                iso = isoBox.getAttribute('data-iso');
                name = isoBox.getAttribute('data-name');
            } else {
                iso = isoBox.value;
                name = isoBox.options[isoBox.selectedIndex].getAttribute('data-name');
            }

            const payload = {
                country_code: code,
                iso_code: iso,
                country_name: name,
                buy_price: parseFloat(document.getElementById('m-buy').value || 0),
                approve_delay: parseInt(document.getElementById('m-delay').value || 0)
            };

            await fetch('/api/admin/sourcing/price/update', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            init();
            closePriceModal();
        }

        async function deletePrice(code, iso) {
            const confirmed = await showConfirm();
            if (!confirmed) return;

            try {
                // Optimistic UI update
                allPrices = allPrices.filter(p => !(p.code === code && p.iso === iso));
                renderPrices(allPrices);

                await fetch(`/api/admin/prices/delete?code=${code}&iso=${iso}&bot=sourcing`, { method: 'DELETE' });
                init();
            } catch (e) {
                console.error(e);
                init();
            }
        }

        // Confirm Modal Logic
        let confirmResolve = null;
        function showConfirm() {
            document.getElementById('confirm-overlay').classList.add('active');
            updateUI(); // Ensure translations are applied
            return new Promise((resolve) => {
                confirmResolve = resolve;
            });
        }

        function renderHistory(list) {
            const container = document.getElementById('history-list');
            if (!list || !list.length) {
                container.innerHTML = `
                <div style="text-align: center; padding: 40px 20px; background: var(--card-glass); border-radius: 16px; border: 1px dashed var(--border); margin-top: 0;">
                    <i class="fas fa-history" style="font-size: 2.5rem; color: var(--text-secondary); opacity: 0.15; margin-bottom: 12px;"></i>
                    <p style="color: var(--text-secondary); font-weight: 600; font-size: 0.95rem;">${translations[currentLang].no_ops}</p>
                </div>`;
                return;
            }
            container.innerHTML = list.map(item => {
                let statusColor = '#f59e0b'; // PENDING
                let statusText = translations[currentLang].st_pending;

                if (item.status === 'AVAILABLE' || item.status === 'SOLD') {
                    statusColor = '#10b981'; // ACCEPTED
                    statusText = translations[currentLang].st_accepted;
                } else if (item.status === 'REJECTED') {
                    statusColor = '#ef4444'; // REJECTED
                    statusText = translations[currentLang].st_rejected;
                }

                const isPending = item.status === 'PENDING' || item.status === 'pending';

                const rowS = "background: var(--bg-elevated); border: 1px solid var(--border); padding: 14px 18px; border-radius: 12px; display: flex; justify-content: space-between; align-items: center; gap: 15px;";
                const lblS = "color: var(--text-secondary); font-size: 0.8rem; font-weight: 700; text-transform: uppercase;";

                return `
                <div class="user-card" style="margin-bottom: 25px; padding-top: 24px;">
                    <div style="display: flex; flex-direction: column; gap: 10px;">
                        <div style="${rowS}">
                            <span style="${lblS}">${translations[currentLang].lbl_status}</span>
                            <span style="color: ${statusColor}; font-weight: 800; font-size: 0.85rem; text-transform: uppercase;">
                                ${statusText}
                            </span>
                        </div>
                        <div style="${rowS}">
                            <span style="${lblS}">${translations[currentLang].lbl_user}</span>
                            <span style="color: #8b5cf6; font-weight: 800; font-size: 1.1rem; text-align: right;">${item.seller_id}</span>
                        </div>
                        <div style="${rowS}">
                            <span style="${lblS}">${translations[currentLang].lbl_number}</span>
                            <span style="color: #8b5cf6; font-weight: 800; font-size: 1.1rem; text-align: right; direction: ltr;">${item.phone}</span>
                        </div>

                        <div style="${rowS}">
                            <span style="${lblS}">${translations[currentLang].lbl_price}</span>
                            <span style="color: #3b82f6; font-weight: 900; font-size: 1.2rem; text-align: right;">$${Number(item.buy_price).toFixed(2)}</span>
                        </div>
                        <div style="${rowS}">
                            <span style="${lblS}">${translations[currentLang].lbl_date}</span>
                            <span class="${isPending ? 'countdown-timer' : ''}" 
                                  data-ready="${item.ready_at}" 
                                  style="color: #fdd835; font-weight: 600; font-size: 0.85rem; text-align: right;">
                                ${isPending ? '...' : item.date}
                            </span>
                        </div>
                    </div>
                </div>
                `;
            }).join('');
        }

        function closeConfirm(result) {
            document.getElementById('confirm-overlay').classList.remove('active');
            if (confirmResolve) {
                confirmResolve(result);
                confirmResolve = null;
            }
        }

        function saveSettings() {
            alert(currentLang === 'ar' ? 'تم حفظ الإعدادات بنجاح!' : 'Settings saved successfully!');
        }

        function updateAllCountdowns() {
            const now = new Date().getTime();
            document.querySelectorAll('.countdown-timer').forEach(el => {
                const readyStr = el.getAttribute('data-ready');
                if (!readyStr || readyStr === 'null') return;

                // Parse numeric timestamp if possible, otherwise use as string
                const readyAt = isNaN(readyStr) ? new Date(readyStr).getTime() : parseInt(readyStr);
                const diff = readyAt - now;

                if (diff <= 0) {
                    el.innerText = translations[currentLang]?.time_processing || "Processing...";
                    el.style.color = '#10b981';
                    return;
                }

                const hours = Math.floor(diff / (1000 * 60 * 60));
                const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
                const seconds = Math.floor((diff % (1000 * 60)) / 1000);

                let hStr = hours > 0 ? hours + ':' : '';
                let mStr = (minutes < 10 && (hours > 0) ? '0' : '') + minutes + ':';
                let sStr = (seconds < 10 ? '0' : '') + seconds;

                el.innerText = hStr + mStr + sStr;
            });
        }
        setInterval(updateAllCountdowns, 1000);

        applyTheme();
        updateUI();
        init();

        const savedView = sessionStorage.getItem('last_view_admin_sourcing') || 'home';
        const menuBtn = document.getElementById('menu-' + (savedView === 'home' ? 'dashboard' : savedView));
        if (menuBtn) switchNav(savedView, menuBtn, true);
        else switchNav(savedView, null, true);
    