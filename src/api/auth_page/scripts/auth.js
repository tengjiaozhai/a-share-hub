document.querySelectorAll('input').forEach((input) => {
  input.addEventListener('focus', () => input.closest('label')?.classList.add('focus'));
  input.addEventListener('blur', () => input.closest('label')?.classList.remove('focus'));
});
