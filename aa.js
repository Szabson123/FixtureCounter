const interval = setInterval(() => {
  const inputs = document.querySelectorAll('td[role="gridcell"] input[type="text"][maxlength="20"]');
  if (inputs.length > 0) {
    inputs.forEach(i => i.maxLength = 50);
  }
}, 300);