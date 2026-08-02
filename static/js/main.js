// Динамическая шапка: уменьшается при прокрутке страницы вниз.
// Порог включения (80px) и выключения (40px) разные — этот "зазор"
// (гистерезис) не даёт классу scrolled мигать туда-сюда, когда
// прокрутка на секунду замирает рядом с одним и тем же значением,
// из-за чего анимация постоянно перезапускалась и шапка "дёргалась".
// requestAnimationFrame ограничивает проверку одним разом за кадр.
(function () {
    var header = document.querySelector('header');
    if (!header) {
        return;
    }

    var ENTER_THRESHOLD = 80;
    var EXIT_THRESHOLD = 40;
    var ticking = false;

    function update() {
        var scrolled = header.classList.contains('scrolled');
        if (!scrolled && window.scrollY > ENTER_THRESHOLD) {
            header.classList.add('scrolled');
        } else if (scrolled && window.scrollY < EXIT_THRESHOLD) {
            header.classList.remove('scrolled');
        }
        ticking = false;
    }

    window.addEventListener('scroll', function () {
        if (!ticking) {
            window.requestAnimationFrame(update);
            ticking = true;
        }
    });
})();

// Синхронизация зазора у логотипа: расстояние от "Рафтинг ЦФО" до
// логотипа должно совпадать с расстоянием от логотипа до "Календарь
// ЦФО". Правая группа пунктов прижата к правому краю шапки (CSS), и
// получившийся зазор справа зависит от ширины контейнера Bootstrap
// (она меняется по брейкпоинтам, а не плавно с шириной окна) — поэтому
// один фиксированный отступ в CSS не может быть верным сразу для всех
// ширин экрана. Здесь этот зазор измеряется по факту и применяется
// слева, при любой ширине окна и в обычном, и в свёрнутом состоянии
// шапки.
(function () {
    var logo = document.querySelector('.logo');
    var navLeft = document.querySelector('.header-nav .nav-left');
    var firstRightLink = document.querySelector('.header-nav .nav-right .nav-link');

    if (!logo || !navLeft || !firstRightLink) {
        return;
    }

    function syncGap() {
        if (window.innerWidth < 992) {
            navLeft.style.paddingRight = '';
            return;
        }

        var logoRect = logo.getBoundingClientRect();
        var rightItemRect = firstRightLink.getBoundingClientRect();
        var navLeftRect = navLeft.getBoundingClientRect();

        var gapRight = rightItemRect.left - logoRect.right;
        var neededPadding = (navLeftRect.right - logoRect.left) + gapRight;

        navLeft.style.paddingRight = Math.max(0, neededPadding) + 'px';
    }

    var resizeTimer = null;
    window.addEventListener('resize', function () {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(syncGap, 100);
    });

    // Логотип и другие элементы шапки анимированы через CSS transition
    // (сжатие при прокрутке) — пересчитываем зазор и по её завершении.
    logo.addEventListener('transitionend', syncGap);

    if (document.fonts && document.fonts.ready) {
        document.fonts.ready.then(syncGap);
    }

    window.addEventListener('load', syncGap);
    syncGap();
})();
