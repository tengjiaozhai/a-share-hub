/* ═══════════════════════════════════════════════════════════
   mobile-nav.js — 移动端导航交互
   汉堡菜单 + 左栏抽屉 + 底部 Tab Bar + 右栏抽屉
   纯原生 JS，无依赖
   ═══════════════════════════════════════════════════════════ */

(function () {
  'use strict';

  /* ── 1. 移动端顶栏注入 ── */
  function injectMobileTopBar() {
    if (document.querySelector('.mobile-top-bar')) return;

    var brand = document.querySelector('.status-bar .brand');
    var brandText = brand ? brand.textContent.trim() : '交易助手';

    var modePill = document.querySelector('.status-bar .pill.mode');
    var modeHTML = modePill ? modePill.outerHTML : '';

    var bar = document.createElement('header');
    bar.className = 'mobile-top-bar';
    bar.innerHTML =
      '<button class="hamburger-btn" id="mobile-hamburger" aria-label="打开菜单" aria-expanded="false">' +
      '<i class="bi bi-list"></i>' +
      '</button>' +
      '<span class="mobile-top-title" id="mobile-title">' + brandText + '</span>' +
      '<div class="mobile-top-actions">' + modeHTML + '</div>';

    var statusBar = document.querySelector('.status-bar');
    if (statusBar && statusBar.parentNode) {
      statusBar.parentNode.insertBefore(bar, statusBar);
    } else {
      document.body.insertBefore(bar, document.body.firstChild);
    }
  }

  /* ── 2. 底部 Tab Bar 注入 ── */
  function injectTabBar() {
    if (document.querySelector('.mobile-tab-bar')) return;

    var tabs = [
      { id: 'view-dashboard', icon: 'bi-search', label: '选股' },
      { id: 'view-alpha', icon: 'bi-graph-up', label: '持仓' },
      { id: 'view-market', icon: 'bi-globe', label: 'A股' },
      { id: 'view-us-stock', icon: 'bi-globe-americas', label: '美股' },
      { id: 'view-fund', icon: 'bi-bank', label: '基金' }
    ];

    var bar = document.createElement('nav');
    bar.className = 'mobile-tab-bar';
    bar.setAttribute('aria-label', '主导航');

    tabs.forEach(function (tab) {
      var btn = document.createElement('button');
      btn.className = 'tab-item';
      btn.setAttribute('data-view', tab.id);
      btn.setAttribute('aria-label', tab.label);
      btn.innerHTML = '<i class="bi ' + tab.icon + '"></i><span>' + tab.label + '</span>';

      var view = document.getElementById(tab.id);
      if (view && view.classList.contains('active')) {
        btn.classList.add('active');
      }

      btn.addEventListener('click', function () {
        // 调用现有 switchView
        var navBtn = document.querySelector('.nav-group button[onclick*="' + tab.id + '"]');
        if (navBtn && typeof switchView === 'function') {
          switchView(navBtn, tab.id);
        } else {
          // Fallback: 直接切换
          document.querySelectorAll('.view').forEach(function (v) {
            v.classList.remove('active');
          });
          var target = document.getElementById(tab.id);
          if (target) target.classList.add('active');
        }

        // 更新 Tab 高亮
        bar.querySelectorAll('.tab-item').forEach(function (t) {
          t.classList.remove('active');
        });
        btn.classList.add('active');

        // 更新标题
        var titleEl = document.getElementById('mobile-title');
        if (titleEl) titleEl.textContent = tab.label;

        // 关闭抽屉
        closeAllDrawers();
      });

      bar.appendChild(btn);
    });

    document.body.appendChild(bar);
  }

  /* ── 3. 抽屉遮罩 ── */
  function injectOverlay() {
    if (document.querySelector('.drawer-overlay')) return;
    var overlay = document.createElement('div');
    overlay.className = 'drawer-overlay';
    overlay.id = 'drawer-overlay';
    overlay.addEventListener('click', closeAllDrawers);
    document.body.appendChild(overlay);
  }

  /* ── 4. 抽屉控制 ── */
  function openDrawer(side) {
    var overlay = document.getElementById('drawer-overlay');
    if (!overlay) return;

    // 关闭所有抽屉先
    closeAllDrawers();

    // 找到对应栏
    var drawer;
    if (side === 'left') {
      // Dashboard 左栏
      drawer = document.querySelector('.rail-left') || document.querySelector('.mkt-rail-left');
    } else if (side === 'right') {
      drawer = document.querySelector('.rail-right') || document.querySelector('.mkt-rail-right');
    }

    if (drawer) {
      drawer.classList.add('drawer-open');
      overlay.classList.add('open');
      drawer.setAttribute('aria-hidden', 'false');
    }
  }

  function closeAllDrawers() {
    var overlay = document.getElementById('drawer-overlay');
    if (!overlay) return;

    document.querySelectorAll('.drawer-open').forEach(function (d) {
      d.classList.remove('drawer-open');
      d.setAttribute('aria-hidden', 'true');
    });
    overlay.classList.remove('open');
  }

  /* ── 5. 汉堡菜单绑定 ── */
  function bindHamburger() {
    var btn = document.getElementById('mobile-hamburger');
    if (!btn) return;

    btn.addEventListener('click', function () {
      var isOpen = document.querySelector('.rail-left.drawer-open, .mkt-rail-left.drawer-open');
      if (isOpen) {
        closeAllDrawers();
        btn.setAttribute('aria-expanded', 'false');
      } else {
        openDrawer('left');
        btn.setAttribute('aria-expanded', 'true');
      }
    });
  }

  /* ── 6. 右栏抽屉触发（长按标题区或专用按钮）── */
  function bindRightDrawerTrigger() {
    var titleEl = document.getElementById('mobile-title');
    if (!titleEl) return;

    var pressTimer = null;

    titleEl.addEventListener('touchstart', function (e) {
      pressTimer = setTimeout(function () {
        openDrawer('right');
        pressTimer = null;
      }, 500);
    });

    titleEl.addEventListener('touchend', function () {
      if (pressTimer) {
        clearTimeout(pressTimer);
        pressTimer = null;
      }
    });

    titleEl.addEventListener('touchmove', function () {
      if (pressTimer) {
        clearTimeout(pressTimer);
        pressTimer = null;
      }
    });
  }

  /* ── 7. ESC 关闭抽屉 ── */
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      closeAllDrawers();
      var btn = document.getElementById('mobile-hamburger');
      if (btn) btn.setAttribute('aria-expanded', 'false');
    }
  });

  /* ── 8. 监听视图切换，同步 Tab 高亮 ── */
  function observeViewSwitch() {
    var observer = new MutationObserver(function (mutations) {
      mutations.forEach(function (m) {
        if (m.attributeName === 'class' && m.target.classList.contains('view')) {
          var activeView = document.querySelector('.view.active');
          if (!activeView) return;

          var viewId = activeView.id;
          var tabBtn = document.querySelector('.tab-item[data-view="' + viewId + '"]');
          if (tabBtn) {
            document.querySelectorAll('.tab-item').forEach(function (t) {
              t.classList.remove('active');
            });
            tabBtn.classList.add('active');

            // 更新标题
            var titleEl = document.getElementById('mobile-title');
            if (titleEl) {
              titleEl.textContent = tabBtn.querySelector('span').textContent;
            }
          }
        }
      });
    });

    document.querySelectorAll('.view').forEach(function (v) {
      observer.observe(v, { attributes: true, attributeFilter: ['class'] });
    });
  }

  /* ── 9. 密度切换 ── */
  window.toggleDensity = function (density) {
    var valid = ['dense', 'normal', 'comfortable'];
    if (valid.indexOf(density) === -1) return;
    document.documentElement.setAttribute('data-density', density);
    try {
      localStorage.setItem('preferred-density', density);
    } catch (e) {}
  };

  // 恢复密度偏好
  try {
    var saved = localStorage.getItem('preferred-density');
    if (saved) {
      window.toggleDensity(saved);
    }
  } catch (e) {}

  /* ── 10. 初始化 ── */
  function init() {
    injectMobileTopBar();
    injectTabBar();
    injectOverlay();
    bindHamburger();
    bindRightDrawerTrigger();
    observeViewSwitch();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
