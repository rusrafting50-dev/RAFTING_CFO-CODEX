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

// Точное позиционирование левой группы пунктов меню (Новости /
// Регионы ЦФО / Рафтинг ЦФО):
//   - левый край "Новости" — строго под левым краем надписи
//     "Федерация рафтинга России";
//   - правый край "Рафтинг ЦФО" — на том же расстоянии от логотипа,
//     что и расстояние от логотипа до "Календарь ЦФО" справа;
//   - "Регионы ЦФО" — точно между ними (justify-content: space-between
//     для 3 пунктов даёт равные промежутки с обеих сторон среднего).
// Оба опорных значения (надпись слева, зазор у логотипа справа)
// зависят от ширины контейнера Bootstrap, которая меняется по
// брейкпоинтам, а не плавно с шириной окна — поэтому единственный
// способ всегда попадать точно — измерять по факту и позиционировать
// левую группу через JS, а не через фиксированные значения в CSS.
(function () {
    var logo = document.querySelector('.logo');
    var navLeft = document.querySelector('.header-nav .nav-left');
    var navbarCollapse = document.querySelector('.header-nav .navbar-collapse');
    var orgNameLeft = document.querySelector('.org-name-left');
    var firstRightLink = document.querySelector('.header-nav .nav-right .nav-link');

    if (!logo || !navLeft || !navbarCollapse || !orgNameLeft || !firstRightLink) {
        return;
    }

    var header = document.querySelector('header');
    var cachedTargetLeft = null;

    // У .nav-link есть собственный горизонтальный padding (Bootstrap
    // --bs-navbar-nav-link-padding-x, 8px) — видимый текст "Новости"
    // начинается на 8px правее левого края своего блока. Чтобы
    // выровнять именно текст (а не блок) с надписью "Федерация
    // рафтинга России", целевой левый край блока сдвигается на эти же
    // 8px влево.
    var NAV_LINK_PADDING_X = 8;

    function syncNavLeft() {
        if (window.innerWidth < 992) {
            navLeft.style.left = '';
            navLeft.style.width = '';
            navLeft.style.paddingRight = '';
            return;
        }

        var collapseRect = navbarCollapse.getBoundingClientRect();

        // Надпись "Федерация рафтинга России" сама уезжает и уменьшается
        // при сжатии шапки (см. предыдущую анимацию), поэтому её текущие
        // координаты в этот момент не отражают положение "в развёрнутом
        // виде". Запоминаем целевой левый край только пока шапка НЕ
        // сжата, а в сжатом состоянии используем последнее сохранённое
        // значение — иначе "Новости" будет "прыгать" вслед за уезжающей
        // надписью.
        if (!header || !header.classList.contains('scrolled')) {
            var orgLeftRect = orgNameLeft.getBoundingClientRect();
            cachedTargetLeft = (orgLeftRect.left - collapseRect.left) - NAV_LINK_PADDING_X;
        }

        if (cachedTargetLeft === null) {
            return;
        }

        var logoRect = logo.getBoundingClientRect();
        var rightItemRect = firstRightLink.getBoundingClientRect();

        // Зазор логотип -> "Календарь ЦФО" (справа) — тот же самый
        // зазор нужен слева, между "Рафтинг ЦФО" и логотипом. Логотип
        // меняет размер при сжатии шапки, поэтому этот зазор пересчитываем
        // всегда, в отличие от левого края.
        var gapAtLogo = rightItemRect.left - logoRect.right;
        var targetRight = (logoRect.left - gapAtLogo) - collapseRect.left;

        navLeft.style.left = cachedTargetLeft + 'px';
        navLeft.style.width = Math.max(0, targetRight - cachedTargetLeft) + 'px';
        navLeft.style.paddingRight = '0';
    }

    var resizeTimer = null;
    window.addEventListener('resize', function () {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(syncNavLeft, 100);
    });

    // Логотип и другие элементы шапки анимированы через CSS transition
    // (сжатие при прокрутке) — пересчитываем позицию и по её завершении.
    logo.addEventListener('transitionend', syncNavLeft);

    if (document.fonts && document.fonts.ready) {
        document.fonts.ready.then(syncNavLeft);
    }

    window.addEventListener('load', syncNavLeft);
    syncNavLeft();
})();
