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

// Ширина левой группы пунктов меню (Новости / Регионы ЦФО / Клубы)
// раньше пересчитывалась здесь через JS (зазор "Клубы -> логотип" должен
// зеркально совпадать с зазором "логотип -> Соревнования" справа) — но
// оказалось, что нужное значение в пикселях НЕ зависит от ширины экрана
// вообще (проверено расчётом от 992px до 3000px — везде одно и то же
// число: логотип центрирован по всей шапке, а обе группы меню
// симметрично привязаны к контейнеру). Поэтому JS здесь больше не
// нужен — ширина прописана фиксированным числом прямо в CSS (см.
// .header-nav .nav-left в style.css).

// Карусель карточек на главной (вкладки "Соревнования" / "Мероприятия"):
// стрелки прокручивают ленту на ширину одной карточки + отступ, а не
// на фиксированное число пикселей — так шаг всегда совпадает с
// реальным размером карточки независимо от ширины экрана.
(function () {
    var CARD_GAP = 16;

    document.querySelectorAll('.home-carousel-widget').forEach(function (carousel) {
        var track = carousel.querySelector('.home-carousel-track');
        var prevBtn = carousel.querySelector('.home-carousel-prev');
        var nextBtn = carousel.querySelector('.home-carousel-next');
        if (!track || !prevBtn || !nextBtn) {
            return;
        }

        function scrollByCard(direction) {
            var card = track.querySelector('.home-carousel-card');
            var step = card ? card.getBoundingClientRect().width + CARD_GAP : track.clientWidth;
            track.scrollBy({ left: direction * step, behavior: 'smooth' });
        }

        prevBtn.addEventListener('click', function () { scrollByCard(-1); });
        nextBtn.addEventListener('click', function () { scrollByCard(1); });
    });
})();

// Слайдер доп. фото на странице новости — та же логика прокрутки на
// ширину одного слайда, что и у карусели на главной.
(function () {
    var SLIDE_GAP = 12;

    document.querySelectorAll('.news-gallery').forEach(function (gallery) {
        var track = gallery.querySelector('.news-gallery-track');
        var prevBtn = gallery.querySelector('.news-gallery-prev');
        var nextBtn = gallery.querySelector('.news-gallery-next');
        if (!track || !prevBtn || !nextBtn) {
            return;
        }

        function scrollBySlide(direction) {
            var slide = track.querySelector('.news-gallery-slide');
            var step = slide ? slide.getBoundingClientRect().width + SLIDE_GAP : track.clientWidth;
            track.scrollBy({ left: direction * step, behavior: 'smooth' });
        }

        prevBtn.addEventListener('click', function () { scrollBySlide(-1); });
        nextBtn.addEventListener('click', function () { scrollBySlide(1); });
    });
})();

// Лайтбокс с миниатюрами: клик по фото (в слайдере новости или в сетке
// альбома "Медиа") открывает увеличенное фото на весь экран (в
// естественных пропорциях, без обрезки) с навигацией вперёд/назад и
// строкой миниатюр внизу. Общий для .news-gallery и .media-album-grid —
// оба типа контейнеров идут парой с .news-lightbox сразу следующим
// элементом в разметке (см. news_detail.html, media_album_detail.html).
(function () {
    document.querySelectorAll('.news-gallery, .media-album-grid').forEach(function (gallery) {
        var slides = Array.prototype.slice.call(gallery.querySelectorAll('[data-full-src]'));
        var lightbox = gallery.nextElementSibling;
        if (!slides.length || !lightbox || !lightbox.classList.contains('news-lightbox')) {
            return;
        }

        var img = lightbox.querySelector('.news-lightbox-img');
        var closeBtn = lightbox.querySelector('.news-lightbox-close');
        var prevBtn = lightbox.querySelector('.news-lightbox-prev');
        var nextBtn = lightbox.querySelector('.news-lightbox-next');
        var thumbs = Array.prototype.slice.call(lightbox.querySelectorAll('.news-lightbox-thumb'));
        var currentIndex = 0;

        function show(index) {
            currentIndex = (index + slides.length) % slides.length;
            img.src = slides[currentIndex].getAttribute('data-full-src');
            thumbs.forEach(function (thumb, i) {
                thumb.classList.toggle('active', i === currentIndex);
            });
            if (thumbs[currentIndex]) {
                thumbs[currentIndex].scrollIntoView({ block: 'nearest', inline: 'center', behavior: 'smooth' });
            }
        }

        function open(index) {
            show(index);
            lightbox.classList.add('open');
            lightbox.setAttribute('aria-hidden', 'false');
        }

        function close() {
            lightbox.classList.remove('open');
            lightbox.setAttribute('aria-hidden', 'true');
            img.src = '';
        }

        slides.forEach(function (slide, index) {
            slide.addEventListener('click', function () { open(index); });
        });

        thumbs.forEach(function (thumb, index) {
            thumb.addEventListener('click', function () { show(index); });
        });

        closeBtn.addEventListener('click', close);
        prevBtn.addEventListener('click', function () { show(currentIndex - 1); });
        nextBtn.addEventListener('click', function () { show(currentIndex + 1); });

        lightbox.addEventListener('click', function (event) {
            if (event.target === lightbox) {
                close();
            }
        });

        document.addEventListener('keydown', function (event) {
            if (!lightbox.classList.contains('open')) {
                return;
            }
            if (event.key === 'Escape') {
                close();
            } else if (event.key === 'ArrowLeft') {
                show(currentIndex - 1);
            } else if (event.key === 'ArrowRight') {
                show(currentIndex + 1);
            }
        });
    });
})();

// Лайтбокс со встроенным плеером видео (YouTube/VK): клик по видео на
// главной или на странице "Медиа" открывает его поверх страницы своим
// плеером, без перехода на сторонний сайт — если ссылка поддерживает
// встраивание (см. video_embed_url в app.py). Иначе data-video-embed
// пуст, обработчик не вешается и клик по ссылке идёт как обычно.
// При открытии сперва показывается обложка видео со значком play —
// сам плеер (iframe) загружается и стартует только по клику на неё.
(function () {
    var lightbox = document.getElementById('videoLightbox');
    var iframe = document.getElementById('videoLightboxIframe');
    var cover = document.getElementById('videoLightboxCover');
    if (!lightbox || !iframe || !cover) {
        return;
    }

    var titleEl = document.getElementById('videoLightboxTitle');
    var linkEl = document.getElementById('videoLightboxLink');
    var closeBtn = lightbox.querySelector('.news-lightbox-close');
    var currentEmbedUrl = '';

    function showCover() {
        iframe.src = 'about:blank';
        cover.hidden = false;
    }

    function playVideo() {
        if (!currentEmbedUrl) {
            return;
        }
        iframe.src = currentEmbedUrl;
        cover.hidden = true;
    }

    function close() {
        lightbox.classList.remove('open');
        lightbox.setAttribute('aria-hidden', 'true');
        showCover();
        currentEmbedUrl = '';
    }

    document.querySelectorAll('[data-video-embed]').forEach(function (trigger) {
        var embedUrl = trigger.getAttribute('data-video-embed');
        if (!embedUrl) {
            return;
        }
        trigger.addEventListener('click', function (event) {
            event.preventDefault();
            currentEmbedUrl = embedUrl;
            cover.style.backgroundImage = "url('" + (trigger.getAttribute('data-video-thumb') || '') + "')";
            showCover();
            titleEl.textContent = trigger.getAttribute('data-video-title') || '';
            linkEl.href = trigger.getAttribute('data-video-url') || '#';
            lightbox.classList.add('open');
            lightbox.setAttribute('aria-hidden', 'false');
        });
    });

    cover.addEventListener('click', playVideo);
    closeBtn.addEventListener('click', close);
    lightbox.addEventListener('click', function (event) {
        if (event.target === lightbox) {
            close();
        }
    });
    document.addEventListener('keydown', function (event) {
        if (lightbox.classList.contains('open') && event.key === 'Escape') {
            close();
        }
    });
})();

// Кнопка "Наверх" на странице новости — прокрутка к началу страницы.
(function () {
    document.querySelectorAll('.scroll-top-btn').forEach(function (btn) {
        btn.addEventListener('click', function () {
            window.scrollTo({ top: 0, behavior: 'smooth' });
        });
    });
})();

// Выпадающие списки День/Месяц/Год над списком новостей: сама раскладка
// списка (открыт/закрыт) — чисто клиентское состояние, а выбор значения
// внутри — обычная ссылка с перезагрузкой страницы. Общий для страницы
// списка новостей и страницы отдельной новости (шапка с фильтром у них
// одна и та же, см. templates/main/_news_filter.html).
(function () {
    var dropdowns = document.querySelectorAll('[data-news-dropdown]');

    function closeAll(except) {
        dropdowns.forEach(function (dd) {
            if (dd !== except) {
                dd.classList.remove('open');
            }
        });
    }

    dropdowns.forEach(function (dropdown) {
        var toggle = dropdown.querySelector('.news-date-toggle');
        if (!toggle) {
            return;
        }
        toggle.addEventListener('click', function (event) {
            event.stopPropagation();
            var isOpen = dropdown.classList.contains('open');
            closeAll(dropdown);
            dropdown.classList.toggle('open', !isOpen);
        });
    });

    document.addEventListener('click', function () {
        closeAll(null);
    });
})();

// Шеврон-раскрывашка категории документов (боковая панель категорий
// «Соревнования → Нормативные документы» и такая же панель на странице
// федерации, regions/_sidebar.html) — один общий обработчик на весь
// сайт вместо копии инлайн-скрипта на каждой странице, где встречается
// класс .doc-category-chevron-btn.
(function () {
    document.querySelectorAll('.doc-category-chevron-btn').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var list = document.getElementById(btn.dataset.target);
            var expanded = btn.getAttribute('aria-expanded') === 'true';
            btn.setAttribute('aria-expanded', String(!expanded));
            list.classList.toggle('is-open', !expanded);
        });
    });
})();

// Название федерации в шапке (страница конкретной федерации,
// .org-name-left .org-title) — логотип центрирован абсолютно по всей
// шапке и не резервирует место в потоке, поэтому длинное название
// ничем не ограничено и может залезать под логотип. Если натуральная
// ширина названия не помещается до начала логотипа с отступом 16px,
// уменьшаем шрифт ровно настолько, чтобы поместилось — вычисляется
// один раз по соотношению доступной ширины к фактической (без цикла
// "уменьшить -> перемерить"), поэтому не дёргается. Только на широких
// экранах (>=992px) — на мобильной раскладке логотип не поверх текста
// (см. media max-width: 991.98px в style.css), там текст просто
// переносится по ширине контейнера как обычно.
(function () {
    var title = document.querySelector('.org-name-left .org-title');
    var logoLink = document.querySelector('.logo-link');
    if (!title || !logoLink) {
        return;
    }

    function fit() {
        if (window.innerWidth < 992) {
            title.style.fontSize = '';
            return;
        }

        // Сброс перед замером — иначе повторный вызов (resize) мерил бы
        // уже уменьшенный текст вместо исходного.
        title.style.fontSize = '';

        var logoLeft = logoLink.getBoundingClientRect().left;
        var titleRect = title.getBoundingClientRect();
        var available = logoLeft - 16 - titleRect.left;

        if (available > 0 && titleRect.width > available) {
            var baseFontSize = parseFloat(window.getComputedStyle(title).fontSize);
            title.style.fontSize = (baseFontSize * (available / titleRect.width)) + 'px';
        }
    }

    fit();
    window.addEventListener('resize', fit);
    if (document.fonts && document.fonts.ready) {
        document.fonts.ready.then(fit);
    }
})();
