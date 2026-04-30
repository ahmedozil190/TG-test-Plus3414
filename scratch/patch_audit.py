import os
import re

file_path = r"d:\9- My Projects\6- Numbers Store Bot\templates\admin_sourcing.html"

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Remove the auditModal div
modal_pattern = re.compile(r'<!-- Audit Modal -->.*?<div id="auditModal".*?</div>\s+</div>', re.DOTALL)
content = modal_pattern.sub('<!-- Scripts below -->', content)

# 2. Replace JS functions
# We use a more specific pattern to avoid issues
old_js_pattern = re.compile(r'async function openAuditModal\(requestId\).*?async function checkAllAuditNumbers\(\) \{.*?\}', re.DOTALL)

new_js = r"""async function openAuditModal(requestId) {
            const container = document.getElementById(`audit-inline-${requestId}`);
            const body = document.getElementById(`audit-body-${requestId}`);
            const startSpan = document.getElementById(`audit-start-${requestId}`);
            
            if (container.style.display === 'block') {
                container.style.display = 'none';
                return;
            }
            
            // Close others
            document.querySelectorAll('.audit-inline-box').forEach(b => {
                if (b.id !== `audit-inline-${requestId}`) b.style.display = 'none';
            });
            
            container.style.display = 'block';
            body.innerHTML = '<tr><td colspan="4" style="text-align:center; padding:30px;"><i class="fas fa-spinner fa-spin"></i> Loading data...</td></tr>';
            
            try {
                const res = await fetch(`/api/admin/withdrawal/${requestId}/audit`);
                const data = await res.json();
                
                const accounts = data.accounts || [];
                startSpan.innerText = data.start_date === "Beginning" ? "User's Start" : formatDateTime(data.start_date);

                if (accounts.length === 0) {
                    body.innerHTML = '<tr><td colspan="4" style="text-align:center; padding:30px;">No numbers found.</td></tr>';
                    return;
                }

                body.innerHTML = accounts.map(acc => `
                    <tr id="audit-row-${acc.id}" style="border-bottom: 1px solid rgba(255,255,255,0.03);">
                        <td style="padding: 10px; font-weight: 700; font-size: 0.85rem; width: 40%; word-break: break-all;">${acc.phone}</td>
                        <td style="padding: 10px; color: #10b981; font-weight: 700; width: 25%;">$${acc.price}</td>
                        <td style="padding: 10px; text-align: center; width: 25%;">
                            <span class="status-badge" style="background: rgba(88, 101, 242, 0.1); color: #8b5cf6; padding: 3px 8px; border-radius: 6px; font-size: 0.7rem; text-transform: capitalize; font-weight: 700;">${acc.status}</span>
                        </td>
                        <td style="padding: 10px; text-align: right; width: 10%;">
                            <button class="pg-btn" onclick="checkOneAuditNumber(${acc.id}, this)" style="padding: 5px 10px; font-size: 0.7rem; background: var(--bg-elevated); border-radius: 8px;">
                                <i class="fas fa-sync"></i>
                            </button>
                        </td>
                    </tr>
                `).join('');
            } catch (e) {
                body.innerHTML = '<tr><td colspan="4" style="text-align:center; padding:30px; color:var(--error);">Error loading data.</td></tr>';
            }
        }

        async function checkOneAuditNumber(accId, btn) {
            const icon = btn.querySelector('i');
            icon.className = 'fas fa-spinner fa-spin';
            btn.disabled = true;

            try {
                const res = await fetch('/api/admin/accounts/check-alive', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ account_id: accId })
                });
                const data = await res.json();
                
                const row = document.getElementById(`audit-row-${accId}`);
                const statusCell = row.querySelectorAll('td')[2];
                
                if (data.status === 'alive') {
                    statusCell.innerHTML = '<span class="status-badge" style="background: rgba(16, 185, 129, 0.1); color: #10b981; padding: 4px 10px; border-radius: 6px; font-size: 0.75rem; font-weight: 700; white-space: nowrap;">ALIVE</span>';
                } else {
                    statusCell.innerHTML = '<span class="status-badge" style="background: rgba(239, 68, 68, 0.1); color: #ef4444; padding: 4px 10px; border-radius: 6px; font-size: 0.75rem; font-weight: 700; white-space: nowrap;">DEAD</span>';
                }
            } catch (e) {
                console.error(e);
            } finally {
                icon.className = 'fas fa-sync';
                btn.disabled = false;
            }
        }

        async function checkAllAuditNumbers(requestId) {
            const container = document.getElementById(`audit-inline-${requestId}`);
            const btns = container.querySelectorAll('.pg-btn');
            for (const btn of btns) {
                const onclick = btn.getAttribute('onclick');
                if (!onclick || !onclick.includes('checkOneAuditNumber')) continue;
                const accId = onclick.match(/\d+/)[0];
                await checkOneAuditNumber(accId, btn);
                await new Promise(r => setTimeout(r, 400));
            }
        }"""

# Use replacement directly without regex sub for the string to avoid escape issues
if old_js_pattern.search(content):
    content = old_js_pattern.sub(lambda m: new_js, content)
    print("JS logic replaced.")
else:
    print("Old JS logic not found via regex.")

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Patching process finished.")
