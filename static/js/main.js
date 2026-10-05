/**
 * IronPulse Fitness & Muscle Tracker - Main JavaScript
 */

document.addEventListener('DOMContentLoaded', () => {
  initThemeToggle();
  initMobileNav();
  initSidebarToggle();
  initModals();
  initAlertDismissal();
  initExerciseFiltering();
  initPageTransitions();
  initFormLoadingStates();
});

// Authenticated Sidebar Toggling (Desktop Collapse & Mobile Drawer)
function initSidebarToggle() {
  const appLayout = document.getElementById('appLayout');
  const collapseBtn = document.getElementById('sidebarCollapseBtn');
  const mobileToggleBtn = document.getElementById('mobileSidebarToggle');
  const backdrop = document.getElementById('sidebarBackdrop');

  if (!appLayout) return;

  // Restore saved desktop collapse preference
  const savedCollapsed = localStorage.getItem('ironpulse_sidebar_collapsed');
  if (savedCollapsed === 'true' && window.innerWidth > 1024) {
    appLayout.classList.add('sidebar-collapsed');
  }

  // Desktop collapse toggle button
  if (collapseBtn) {
    collapseBtn.addEventListener('click', () => {
      appLayout.classList.toggle('sidebar-collapsed');
      const isCollapsed = appLayout.classList.contains('sidebar-collapsed');
      localStorage.setItem('ironpulse_sidebar_collapsed', isCollapsed ? 'true' : 'false');
    });
  }

  // Mobile drawer toggle
  if (mobileToggleBtn) {
    mobileToggleBtn.addEventListener('click', () => {
      appLayout.classList.toggle('sidebar-mobile-open');
    });
  }

  // Close mobile drawer on backdrop click
  if (backdrop) {
    backdrop.addEventListener('click', () => {
      appLayout.classList.remove('sidebar-mobile-open');
    });
  }

  // Close mobile drawer on escape key
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && appLayout.classList.contains('sidebar-mobile-open')) {
      appLayout.classList.remove('sidebar-mobile-open');
    }
  });
}

function toggleSidebar() {
  const appLayout = document.getElementById('appLayout');
  if (appLayout) {
    appLayout.classList.toggle('sidebar-collapsed');
    const isCollapsed = appLayout.classList.contains('sidebar-collapsed');
    localStorage.setItem('ironpulse_sidebar_collapsed', isCollapsed ? 'true' : 'false');
  }
}

// Mobile Navigation Toggle
function initMobileNav() {
  const toggleBtn = document.getElementById('navToggleBtn');
  const navLinks = document.getElementById('navLinks');

  if (toggleBtn && navLinks) {
    toggleBtn.addEventListener('click', () => {
      navLinks.classList.toggle('open');
      const isExpanded = navLinks.classList.contains('open');
      toggleBtn.setAttribute('aria-expanded', isExpanded);
    });

    // Close when clicking outside
    document.addEventListener('click', (e) => {
      if (!navLinks.contains(e.target) && !toggleBtn.contains(e.target) && navLinks.classList.contains('open')) {
        navLinks.classList.remove('open');
      }
    });
  }
}

// Modal System
function initModals() {
  // Open modal buttons: data-modal-target="#modalId"
  const modalOpenBtns = document.querySelectorAll('[data-modal-target]');
  modalOpenBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const targetId = btn.getAttribute('data-modal-target');
      const modal = document.querySelector(targetId);
      if (modal) {
        openModal(modal);
      }
    });
  });

  // Close modal buttons: data-modal-close
  const modalCloseBtns = document.querySelectorAll('[data-modal-close]');
  modalCloseBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const modal = btn.closest('.modal-backdrop');
      if (modal) {
        closeModal(modal);
      }
    });
  });

  // Close on clicking backdrop outside modal dialog
  const modals = document.querySelectorAll('.modal-backdrop');
  modals.forEach(modal => {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) {
        closeModal(modal);
      }
    });
  });

  // Close on Escape key
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      const openModalEl = document.querySelector('.modal-backdrop.open');
      if (openModalEl) {
        closeModal(openModalEl);
      }
    }
  });
}

function openModal(modal) {
  modal.classList.add('open');
  document.body.style.overflow = 'hidden';
}

function closeModal(modal) {
  modal.classList.remove('open');
  document.body.style.overflow = '';
}

// Flash Alert Dismissal
function initAlertDismissal() {
  const closeAlertBtns = document.querySelectorAll('.alert-close');
  closeAlertBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const alert = btn.closest('.alert');
      if (alert) {
        alert.style.opacity = '0';
        alert.style.transform = 'translateY(-6px)';
        setTimeout(() => alert.remove(), 250);
      }
    });
  });

  // Auto-fade alerts after 5 seconds
  setTimeout(() => {
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
      alert.style.transition = 'all 0.4s ease';
      alert.style.opacity = '0';
      setTimeout(() => alert.remove(), 400);
    });
  }, 5000);
}

// Exercise Library Real-Time Client Search & Filters
function initExerciseFiltering() {
  const searchInput = document.getElementById('exerciseSearchInput');
  const cards = document.querySelectorAll('.exercise-card');
  const categoryFilters = document.querySelectorAll('.filter-chip[data-category]');
  const countDisplay = document.getElementById('exerciseCountDisplay');

  if (!cards.length) return;

  let activeCategory = 'All';
  let activeSearch = '';

  function filterExercises() {
    let visibleCount = 0;

    cards.forEach(card => {
      const cardCategory = card.getAttribute('data-category') || '';
      const cardName = (card.getAttribute('data-name') || '').toLowerCase();
      const cardMuscle = (card.getAttribute('data-muscles') || '').toLowerCase();
      const cardEquipment = (card.getAttribute('data-equipment') || '').toLowerCase();

      const matchesCategory = (activeCategory === 'All' || cardCategory.toLowerCase() === activeCategory.toLowerCase());
      const query = activeSearch.toLowerCase().trim();
      const matchesSearch = !query || 
                            cardName.includes(query) || 
                            cardMuscle.includes(query) || 
                            cardEquipment.includes(query);

      if (matchesCategory && matchesSearch) {
        card.style.display = '';
        visibleCount++;
      } else {
        card.style.display = 'none';
      }
    });

    if (countDisplay) {
      countDisplay.textContent = `${visibleCount} exercises found`;
    }
  }

  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      activeSearch = e.target.value;
      filterExercises();
    });
  }

  categoryFilters.forEach(chip => {
    chip.addEventListener('click', (e) => {
      e.preventDefault();
      categoryFilters.forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
      activeCategory = chip.getAttribute('data-category');
      filterExercises();
    });
  });
}

// ===================================================================
// Theme Toggle & Persistent Preference System
// ===================================================================
function initThemeToggle() {
  const savedTheme = localStorage.getItem('ironpulse_theme') || 'dark';
  applyTheme(savedTheme, false);

  // 1. Sidebar Theme Toggle Button
  const sidebarToggle = document.getElementById('sidebarThemeToggle');
  if (sidebarToggle) {
    sidebarToggle.addEventListener('click', () => {
      const current = document.documentElement.getAttribute('data-theme') || 'dark';
      const next = current === 'light' ? 'dark' : 'light';
      applyTheme(next, true);
    });
  }

  // 2. Compact Theme Toggle Buttons (Topbar, Public Navbar)
  const compactToggles = document.querySelectorAll('.js-theme-toggle, .theme-toggle-compact');
  compactToggles.forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const current = document.documentElement.getAttribute('data-theme') || 'dark';
      const next = current === 'light' ? 'dark' : 'light';
      applyTheme(next, true);
    });
  });

  // 3. Settings Segmented Choice Buttons
  const settingsBtns = document.querySelectorAll('[data-theme-choice]');
  settingsBtns.forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const chosen = btn.getAttribute('data-theme-choice');
      if (chosen) {
        applyTheme(chosen, true);
      }
    });
  });
}

function applyTheme(theme, save = true) {
  document.documentElement.setAttribute('data-theme', theme);
  if (save) {
    try {
      localStorage.setItem('ironpulse_theme', theme);
    } catch (e) {}
  }

  // Update label text in sidebar
  const sidebarLabels = document.querySelectorAll('.theme-label-text');
  sidebarLabels.forEach(el => {
    el.textContent = theme === 'light' ? 'Light Mode' : 'Dark Mode';
  });

  // Update active status on settings buttons
  const settingsBtns = document.querySelectorAll('[data-theme-choice]');
  settingsBtns.forEach(btn => {
    if (btn.getAttribute('data-theme-choice') === theme) {
      btn.classList.add('active');
    } else {
      btn.classList.remove('active');
    }
  });

  // Update global Chart.js defaults if available
  if (window.Chart) {
    const isLight = theme === 'light';
    Chart.defaults.color = isLight ? '#64748b' : '#94a3b8';
    Chart.defaults.borderColor = isLight ? 'rgba(0, 0, 0, 0.06)' : 'rgba(255, 255, 255, 0.08)';
  }

  // Broadcast event for custom page charts and dynamic listeners
  window.dispatchEvent(new CustomEvent('ironpulse:themechange', { detail: { theme } }));
}

// Chart color helper for light/dark theme adaptation
window.getChartThemeColors = function() {
  const isLight = document.documentElement.getAttribute('data-theme') === 'light';
  return {
    isLight: isLight,
    text: isLight ? '#64748b' : '#94a3b8',
    grid: isLight ? 'rgba(0, 0, 0, 0.06)' : 'rgba(255, 255, 255, 0.05)',
    border: isLight ? '#e2e8f0' : 'rgba(255, 255, 255, 0.08)',
    tooltipBg: isLight ? '#ffffff' : '#121824',
    tooltipTitle: isLight ? '#0f172a' : '#ffffff',
    tooltipBody: isLight ? '#475569' : '#f1f5f9',
    tooltipBorder: isLight ? '#cbd5e1' : '#1e293d'
  };
};

// ===================================================================
// Phase 6: Page Transitions & Universal Request Loading States
// ===================================================================

function initPageTransitions() {
  const bar = document.getElementById('pageTransitionBar');
  if (!bar) return;

  // Complete and fade out when current page completes loading
  bar.classList.add('done');
  setTimeout(() => {
    bar.classList.remove('active', 'done');
    bar.style.width = '0%';
  }, 450);

  // Intercept internal page link clicks for smooth top loader
  document.addEventListener('click', (e) => {
    const link = e.target.closest('a');
    if (!link) return;

    const href = link.getAttribute('href');
    const target = link.getAttribute('target');
    const download = link.hasAttribute('download');

    // Skip anchor hashes, JS actions, email links, external links, and downloads
    if (!href || href.startsWith('#') || href.startsWith('javascript:') || href.startsWith('mailto:') || href.startsWith('tel:') || target === '_blank' || download) {
      return;
    }

    // Check if it's an internal link
    try {
      const url = new URL(link.href, window.location.href);
      if (url.origin !== window.location.origin) return;
    } catch(err) {
      return;
    }

    // Trigger transition progress
    bar.classList.remove('done');
    bar.classList.add('active');
    bar.style.width = '25%';

    setTimeout(() => {
      if (bar.classList.contains('active')) {
        bar.style.width = '70%';
      }
    }, 120);

    setTimeout(() => {
      if (bar.classList.contains('active')) {
        bar.style.width = '90%';
      }
    }, 450);
  });
}

function initFormLoadingStates() {
  document.addEventListener('submit', (e) => {
    const form = e.target;
    // Allow forms to opt out with data-no-loader="true"
    if (form.getAttribute('data-no-loader') === 'true') return;

    const submitBtn = form.querySelector('button[type="submit"], input[type="submit"]');
    if (!submitBtn) return;

    // Prevent duplicate rapid submissions if already pending
    if (submitBtn.classList.contains('is-loading')) {
      e.preventDefault();
      return;
    }

    const customText = submitBtn.getAttribute('data-loading-text');
    setButtonLoading(submitBtn, true, customText);
  });
}

function setButtonLoading(btn, isLoading, customText) {
  if (!btn) return;

  if (isLoading) {
    if (!btn.dataset.originalHtml) {
      btn.dataset.originalHtml = btn.innerHTML;
    }
    btn.classList.add('is-loading');
    btn.disabled = true;

    const text = customText || btn.getAttribute('data-loading-text') || 'Processing...';
    btn.innerHTML = `<span class="btn-spinner"></span><span>${text}</span>`;
  } else {
    btn.classList.remove('is-loading');
    btn.disabled = false;
    if (btn.dataset.originalHtml) {
      btn.innerHTML = btn.dataset.originalHtml;
    }
  }
}

// Global Toast Notifications
function showToast(message, type = 'success') {
  let container = document.querySelector('.flash-container');
  if (!container) {
    container = document.createElement('div');
    container.className = 'flash-container';
    const body = document.querySelector('.app-content-body') || document.querySelector('main') || document.body;
    body.insertBefore(container, body.firstChild);
  }
  const alert = document.createElement('div');
  alert.className = `alert alert-${type}`;
  alert.style.display = 'flex';
  alert.style.alignItems = 'center';
  alert.style.justifyContent = 'space-between';
  alert.innerHTML = `
    <span>${message}</span>
    <button type="button" class="alert-close" aria-label="Close" style="background:none;border:none;color:inherit;font-size:1.2rem;cursor:pointer;">&times;</button>
  `;
  container.appendChild(alert);
  alert.querySelector('.alert-close').addEventListener('click', () => {
    alert.style.opacity = '0';
    alert.style.transform = 'translateY(-6px)';
    setTimeout(() => alert.remove(), 250);
  });
  setTimeout(() => {
    if (alert.parentNode) {
      alert.style.transition = 'all 0.4s ease';
      alert.style.opacity = '0';
      setTimeout(() => alert.remove(), 400);
    }
  }, 4000);
}

// Global Avatar Synchronizer across entire DOM
function syncAvatarEverywhere(avatarUrl, initials) {
  const timestamp = Date.now();
  const freshUrl = avatarUrl ? `${avatarUrl}?t=${timestamp}` : null;

  if (freshUrl) {
    // 1. Update all image avatars on page
    document.querySelectorAll('.pfp-sync-avatar').forEach(img => {
      img.src = freshUrl;
      img.style.display = '';
    });
    // 2. Hide initials avatars
    document.querySelectorAll('.pfp-sync-initials').forEach(div => {
      div.style.display = 'none';
    });
    // Profile page specific elements
    const pfpImg = document.getElementById('pfpCurrentImg');
    const pfpInitials = document.getElementById('pfpInitialsFallback');
    if (pfpImg) {
      pfpImg.src = freshUrl;
      pfpImg.style.display = 'block';
    }
    if (pfpInitials) pfpInitials.style.display = 'none';

    // Update buttons
    const removeBtn = document.getElementById('btnRemovePfp');
    if (removeBtn) removeBtn.style.display = 'inline-flex';

    const uploadText = document.getElementById('pfpUploadBtnText');
    if (uploadText) uploadText.textContent = 'Change Photo';
  } else {
    // Revert to default initials avatar
    document.querySelectorAll('.pfp-sync-avatar').forEach(img => {
      img.style.display = 'none';
    });
    document.querySelectorAll('.pfp-sync-initials').forEach(div => {
      div.style.display = 'flex';
      if (initials) div.textContent = initials;
    });
    const pfpImg = document.getElementById('pfpCurrentImg');
    const pfpInitials = document.getElementById('pfpInitialsFallback');
    if (pfpImg) pfpImg.style.display = 'none';
    if (pfpInitials) {
      pfpInitials.style.display = 'flex';
      if (initials) pfpInitials.textContent = initials;
    }

    // Hide remove button
    const removeBtn = document.getElementById('btnRemovePfp');
    if (removeBtn) removeBtn.style.display = 'none';

    const uploadText = document.getElementById('pfpUploadBtnText');
    if (uploadText) uploadText.textContent = 'Upload Photo';
  }
}

// Profile Picture File Picker and AJAX Flow
function initProfilePictureManagement() {
  const fileInput = document.getElementById('pfpInputFile');
  const triggerBtn = document.getElementById('btnTriggerPfpUpload');
  const previewModal = document.getElementById('modalPfpPreview');
  const previewImg = document.getElementById('pfpPreviewImg');
  const previewInfo = document.getElementById('pfpPreviewInfo');
  const confirmUploadBtn = document.getElementById('btnConfirmPfpUpload');
  const removeModal = document.getElementById('modalPfpRemove');
  const removeTriggerBtn = document.getElementById('btnRemovePfp');
  const confirmRemoveBtn = document.getElementById('btnConfirmRemovePfp');

  if (!fileInput) return;

  let selectedFile = null;

  if (triggerBtn) {
    triggerBtn.addEventListener('click', () => {
      fileInput.click();
    });
  }

  // Remove photo modal trigger
  if (removeTriggerBtn && removeModal) {
    removeTriggerBtn.addEventListener('click', (e) => {
      e.preventDefault();
      removeModal.classList.add('open');
    });
  }

  // Cancel / close preview modal
  if (previewModal) {
    const cancelPreviewBtns = previewModal.querySelectorAll('[data-modal-close], .btn-cancel-pfp-preview');
    cancelPreviewBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        fileInput.value = '';
        selectedFile = null;
        previewModal.classList.remove('open');
      });
    });
    previewModal.addEventListener('click', (e) => {
      if (e.target === previewModal) {
        fileInput.value = '';
        selectedFile = null;
        previewModal.classList.remove('open');
      }
    });
  }

  // Cancel / close remove modal
  if (removeModal) {
    const cancelRemoveBtns = removeModal.querySelectorAll('[data-modal-close], .btn-cancel-pfp-remove');
    cancelRemoveBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        removeModal.classList.remove('open');
      });
    });
  }

  // File chosen in input
  fileInput.addEventListener('change', () => {
    if (!fileInput.files || fileInput.files.length === 0) return;
    const file = fileInput.files[0];

    // File validation: Size <= 5 MB
    const maxSize = 5 * 1024 * 1024;
    if (file.size > maxSize) {
      showToast('Image must be smaller than 5 MB', 'danger');
      fileInput.value = '';
      return;
    }

    // File validation: Allowed image types
    const allowedTypes = ['image/jpeg', 'image/png', 'image/webp', 'image/jpg'];
    if (!allowedTypes.includes(file.type.toLowerCase())) {
      showToast('Please select a valid image (JPG, PNG, or WEBP)', 'danger');
      fileInput.value = '';
      return;
    }

    selectedFile = file;

    // Load preview
    const reader = new FileReader();
    reader.onload = (e) => {
      if (previewImg) previewImg.src = e.target.result;
      if (previewInfo) {
        const sizeKb = Math.round(file.size / 1024);
        const sizeText = sizeKb > 1024 ? `${(sizeKb / 1024).toFixed(1)} MB` : `${sizeKb} KB`;
        previewInfo.textContent = `${file.name} (${sizeText})`;
      }
      if (previewModal) previewModal.classList.add('open');
    };
    reader.readAsDataURL(file);
  });

  // Confirm Upload handler
  if (confirmUploadBtn) {
    confirmUploadBtn.addEventListener('click', async () => {
      if (!selectedFile) return;

      const originalText = confirmUploadBtn.innerHTML;
      confirmUploadBtn.disabled = true;
      confirmUploadBtn.innerHTML = '<span class="btn-spinner"></span> Uploading...';

      const formData = new FormData();
      formData.append('profile_picture', selectedFile);

      try {
        const response = await fetch('/profile/picture/upload', {
          method: 'POST',
          body: formData,
          headers: {
            'X-Requested-With': 'XMLHttpRequest'
          }
        });

        const data = await response.json();

        if (response.ok && data.success) {
          syncAvatarEverywhere(data.avatar_url);
          showToast(data.message || 'Profile picture updated successfully', 'success');
          if (previewModal) previewModal.classList.remove('open');
          fileInput.value = '';
          selectedFile = null;
        } else {
          showToast(data.message || 'Please select a valid image', 'danger');
        }
      } catch (err) {
        console.error('PFP Upload Error:', err);
        showToast('Upload failed. Please check your connection and try again.', 'danger');
      } finally {
        confirmUploadBtn.disabled = false;
        confirmUploadBtn.innerHTML = originalText;
      }
    });
  }

  // Confirm Remove handler
  if (confirmRemoveBtn) {
    confirmRemoveBtn.addEventListener('click', async () => {
      const originalText = confirmRemoveBtn.innerHTML;
      confirmRemoveBtn.disabled = true;
      confirmRemoveBtn.innerHTML = '<span class="btn-spinner"></span> Removing...';

      try {
        const response = await fetch('/profile/picture/remove', {
          method: 'POST',
          headers: {
            'X-Requested-With': 'XMLHttpRequest'
          }
        });

        const data = await response.json();

        if (response.ok && data.success) {
          syncAvatarEverywhere(null, data.initials);
          showToast(data.message || 'Profile picture removed', 'info');
          if (removeModal) removeModal.classList.remove('open');
        } else {
          showToast(data.message || 'Could not remove profile picture.', 'danger');
        }
      } catch (err) {
        console.error('PFP Remove Error:', err);
        showToast('Removal failed. Please try again.', 'danger');
      } finally {
        confirmRemoveBtn.disabled = false;
        confirmRemoveBtn.innerHTML = originalText;
      }
    });
  }
}

document.addEventListener('DOMContentLoaded', () => {
  initProfilePictureManagement();
});

// Global exposure
window.setButtonLoading = setButtonLoading;
window.showToast = showToast;
window.syncAvatarEverywhere = syncAvatarEverywhere;


