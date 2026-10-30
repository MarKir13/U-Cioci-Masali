/* Keep Classic's responsive module relocation; own the mobile drawer interaction. */
document.addEventListener('DOMContentLoaded', function () {
  var toggle = document.getElementById('menu-icon');
  var menu = document.getElementById('mobile_top_menu_wrapper');
  if (!toggle || !menu) return;

  function updateExpandedState() {
    toggle.setAttribute('aria-expanded', String(getComputedStyle(menu).display !== 'none'));
  }

  new MutationObserver(updateExpandedState).observe(menu, {
    attributes: true,
    attributeFilter: ['style', 'class']
  });
  updateExpandedState();

  var backdrop = document.querySelector('.ciocia-menu-backdrop');
  var closeButton = menu.querySelector('.ciocia-menu-close');
  var previousOverflow;
  var inertElements = [];
  function setDrawer(open) {
    if (open === (toggle.getAttribute('aria-expanded') === 'true')) return;
    if (open) {
      previousOverflow = document.body.style.overflow;
      document.body.style.overflow = 'hidden';
      inertElements = Array.from(document.querySelectorAll('#wrapper, #footer')).filter(function (el) { return !el.inert; });
      inertElements.forEach(function (el) { el.inert = true; });
      menu.setAttribute('role', 'dialog');
      menu.setAttribute('aria-modal', 'true');
      menu.setAttribute('aria-labelledby', 'ciocia-menu-title');
    } else {
      document.body.style.overflow = previousOverflow;
      inertElements.forEach(function (el) { el.inert = false; });
      menu.removeAttribute('role');
      menu.removeAttribute('aria-modal');
      menu.removeAttribute('aria-labelledby');
    }
    menu.style.display = open ? 'flex' : 'none';
    backdrop.hidden = !open;
    updateExpandedState();
    if (open) closeButton.focus();
    else toggle.focus();
  }
  // Capture before Classic's delegated click handler, which hides page content.
  toggle.addEventListener('click', function (event) {
    event.preventDefault();
    event.stopImmediatePropagation();
    setDrawer(toggle.getAttribute('aria-expanded') !== 'true');
  }, true);
  closeButton.addEventListener('click', function () { setDrawer(false); });
  backdrop.addEventListener('click', function () { setDrawer(false); });
  menu.addEventListener('keydown', function (event) {
    if (event.key === 'Escape' && event.target === closeButton) {
      event.preventDefault();
      setDrawer(false);
      return;
    }
    if (event.key !== 'Tab') return;
    var focusable = Array.from(menu.querySelectorAll('a, button, input, select')).filter(function (el) {
      return el.getClientRects().length && !el.closest('[hidden]');
    });
    if (event.shiftKey && document.activeElement === focusable[0]) {
      event.preventDefault();
      focusable[focusable.length - 1].focus();
    } else if (!event.shiftKey && document.activeElement === focusable[focusable.length - 1]) {
      event.preventDefault();
      focusable[0].focus();
    }
  });
  window.matchMedia('(min-width: 768px)').addEventListener('change', function (event) {
    if (event.matches) setDrawer(false);
  });

  var currencyToggle = document.getElementById('ciocia-currency-toggle');
  if (currencyToggle) {
    var currencyMenu = currencyToggle.parentElement.querySelector('.dropdown-menu');
    function currencyLinks() {
      return Array.from(currencyMenu.querySelectorAll('a'));
    }
    function closeCurrency() {
      if (currencyToggle.getAttribute('aria-expanded') === 'true') currencyToggle.click();
    }
    currencyToggle.addEventListener('keydown', function (event) {
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault();
        event.stopPropagation();
        if (currencyToggle.getAttribute('aria-expanded') !== 'true') currencyToggle.click();
        var links = currencyLinks();
        if (links.length) links[event.key === 'ArrowDown' ? 0 : links.length - 1].focus();
      } else if (event.key === 'Escape') {
        event.preventDefault();
        event.stopPropagation();
        closeCurrency();
      }
    });
    currencyMenu.addEventListener('keydown', function (event) {
      if (event.key === 'Escape') {
        event.preventDefault();
        event.stopPropagation();
        closeCurrency();
        currencyToggle.focus();
      } else if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault();
        event.stopPropagation();
        var links = currencyLinks();
        var index = links.indexOf(document.activeElement);
        links[(index + (event.key === 'ArrowDown' ? 1 : -1) + links.length) % links.length].focus();
      }
    });
    currencyToggle.parentElement.addEventListener('focusout', function (event) {
      if (!currencyToggle.parentElement.contains(event.relatedTarget)) closeCurrency();
    });
  }

  // Keep category navigation usable without a mouse, at every menu depth.
  var categoryMenu = document.getElementById('top-menu');
  if (!categoryMenu) return;
  var items = Array.from(categoryMenu.querySelectorAll('.ciocia-has-submenu'));

  function controls(item) {
    return {
      button: Array.from(item.children).find(function (el) { return el.classList.contains('ciocia-submenu-toggle'); }),
      panel: Array.from(item.children).find(function (el) { return el.classList.contains('ciocia-submenu'); })
    };
  }

  function setOpen(item, open) {
    var parts = controls(item);
    if (!parts.button || !parts.panel) return;
    parts.button.setAttribute('aria-expanded', String(open));
    parts.panel.hidden = !open;
    if (!open) {
      item.querySelectorAll('.ciocia-has-submenu').forEach(function (child) { setOpen(child, false); });
    }
  }

  items.forEach(function (item) {
    var parts = controls(item);
    if (!parts.button || !parts.panel) return;
    parts.button.addEventListener('click', function () {
      setOpen(item, parts.button.getAttribute('aria-expanded') !== 'true');
    });
    item.addEventListener('mouseenter', function () {
      if (window.matchMedia('(min-width: 768px)').matches) setOpen(item, true);
    });
    item.addEventListener('mouseleave', function () {
      if (!item.contains(document.activeElement) && window.matchMedia('(min-width: 768px)').matches) setOpen(item, false);
    });
    item.addEventListener('focusout', function (event) {
      if (!item.contains(event.relatedTarget)) setOpen(item, false);
    });
  });

  categoryMenu.addEventListener('keydown', function (event) {
    var item = event.target.closest('.ciocia-has-submenu');
    if (event.key === 'Escape' && item) {
      // Close the nearest open submenu and return focus to its own toggle.
      while (item && controls(item).panel.hidden) {
        item = item.parentElement.closest('.ciocia-has-submenu');
      }
      if (item) {
        event.preventDefault();
        setOpen(item, false);
        controls(item).button.focus();
      }
      return;
    }
    if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return;
    var panel;
    if (item && event.target.parentElement === item) {
      setOpen(item, true);
      panel = controls(item).panel;
    } else {
      panel = event.target.closest('.ciocia-submenu');
    }
    if (!panel) return;
    var links = Array.from(panel.querySelectorAll('a, button')).filter(function (el) {
      return !el.closest('[hidden]') && el.getClientRects().length;
    });
    if (!links.length) return;
    event.preventDefault();
    var index = links.indexOf(event.target);
    var next = index < 0 ? (event.key === 'ArrowDown' ? 0 : links.length - 1) :
      (index + (event.key === 'ArrowDown' ? 1 : -1) + links.length) % links.length;
    links[next].focus();
  });

  // Escape also closes the complete mobile menu when no submenu is open.
  menu.addEventListener('keydown', function (event) {
    if (event.key === 'Escape' && !categoryMenu.querySelector('.ciocia-submenu-toggle[aria-expanded="true"]')) {
      if (!event.defaultPrevented && toggle.getAttribute('aria-expanded') === 'true') {
        event.preventDefault();
        toggle.click();
        toggle.focus();
      }
    }
  });
  window.matchMedia('(min-width: 768px)').addEventListener('change', function () {
    items.forEach(function (item) { setOpen(item, false); });
  });
});
