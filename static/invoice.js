// Invoice management - dynamic items and total calculation

let itemCounter = 0;
const itemsContainer = document.getElementById('itemsContainer');
const totalAmountDisplay = document.getElementById('totalAmount');
const itemsDataInput = document.getElementById('itemsData');
const invoiceForm = document.getElementById('invoiceForm');

// Add initial item row on page load
document.addEventListener('DOMContentLoaded', () => {
  addItemRow();
});

// Add item button
document.getElementById('addItemBtn').addEventListener('click', () => {
  addItemRow();
});

// Reset button
document.getElementById('resetBtn').addEventListener('click', () => {
  itemsContainer.innerHTML = '';
  itemCounter = 0;
  addItemRow();
  updateTotal();
});

// Form submission
invoiceForm.addEventListener('submit', (e) => {
  const items = collectItems();
  if (items.length === 0) {
    e.preventDefault();
    alert('Please add at least one item to the invoice.');
    return;
  }
  itemsDataInput.value = JSON.stringify(items);
});

function addItemRow() {
  itemCounter++;
  const rowId = `item-${itemCounter}`;

  const row = document.createElement('div');
  row.className = 'invoice-item-row';
  row.id = rowId;
  row.innerHTML = `
    <div class="invoice-grid">
      <input type="text" placeholder="Item/Service Name" class="item-name" required />
      <input type="number" placeholder="Qty" class="item-quantity" min="1" step="1" value="1" required />
      <input type="number" placeholder="Unit Price" class="item-price" min="0" step="0.01" required />
      <input type="text" class="item-total" readonly value="$0.00" />
      <button type="button" class="delete-item-btn" title="Remove item">×</button>
    </div>
  `;

  itemsContainer.appendChild(row);

  // Add event listeners for calculation
  const qtyInput = row.querySelector('.item-quantity');
  const priceInput = row.querySelector('.item-price');
  const deleteBtn = row.querySelector('.delete-item-btn');

  qtyInput.addEventListener('input', () => updateRowTotal(row));
  priceInput.addEventListener('input', () => updateRowTotal(row));
  deleteBtn.addEventListener('click', () => {
    row.remove();
    updateTotal();
  });

  updateTotal();
}

function updateRowTotal(row) {
  const qty = parseFloat(row.querySelector('.item-quantity').value) || 0;
  const price = parseFloat(row.querySelector('.item-price').value) || 0;
  const total = qty * price;

  row.querySelector('.item-total').value = `$${total.toFixed(2)}`;
  updateTotal();
}

function updateTotal() {
  const rows = itemsContainer.querySelectorAll('.invoice-item-row');
  let grandTotal = 0;

  rows.forEach(row => {
    const qty = parseFloat(row.querySelector('.item-quantity').value) || 0;
    const price = parseFloat(row.querySelector('.item-price').value) || 0;
    grandTotal += qty * price;
  });

  totalAmountDisplay.textContent = `$${grandTotal.toFixed(2)}`;
}

function collectItems() {
  const rows = itemsContainer.querySelectorAll('.invoice-item-row');
  const items = [];

  rows.forEach(row => {
    const name = row.querySelector('.item-name').value.trim();
    const qty = parseFloat(row.querySelector('.item-quantity').value) || 0;
    const price = parseFloat(row.querySelector('.item-price').value) || 0;

    if (name && qty > 0 && price >= 0) {
      items.push({
        name: name,
        quantity: qty,
        unit_price: price,
        total: qty * price
      });
    }
  });

  return items;
}
