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

// Логотип на баннере странице федерации/клуба (.fed-banner-logo img):
// увеличиваем по высоте только длинные горизонтальные логотипы (ширина
// файла минимум вдвое больше высоты) — именно такие в круглой
// миниатюре карточки клуба сжимаются в едва заметную узкую полоску, а
// на прямоугольном баннере под них есть место. Для них высота
// подгоняется под 1/2 высоты баннера. Остальные логотипы (квадратные,
// вертикальные, умеренно вытянутые) не трогаем — они и так помещаются
// в круглой миниатюре нормально, растягивать их не нужно (см. пример:
// широкий wordmark-логотип "Академия" растягивался почти на всю
// ширину баннера при подгонке под 1/3 высоты для всех подряд —
// компактный логотип "Раменский клуб туристов" в этом не нуждался).
// Считаем по naturalWidth/naturalHeight — это соотношение сторон файла,
// не зависит от того, как логотип отрисован сейчас.
(function () {
    var images = document.querySelectorAll('.fed-banner-logo img');
    if (!images.length) {
        return;
    }

    function apply(img) {
        var banner = img.closest('.fed-banner');
        if (banner && img.naturalWidth >= img.naturalHeight * 2) {
            var target = banner.getBoundingClientRect().height / 2;
            img.style.height = target + 'px';
            img.style.width = 'auto';
        }
        // Видимым делаем только здесь, уже после решения — нужный размер
        // логотип получает раньше, чем зритель успевает его увидеть,
        // без «скачка» между исходным и пересчитанным размером
        // (visibility: hidden по умолчанию задан в style.css).
        img.style.visibility = 'visible';
    }

    images.forEach(function (img) {
        if (img.complete && img.naturalWidth) {
            apply(img);
        } else {
            img.addEventListener('load', function () {
                apply(img);
            });
            // Битая картинка не загрузится никогда — не оставляем логотип
            // невидимым навсегда, снимаем visibility и в этом случае.
            img.addEventListener('error', function () {
                img.style.visibility = 'visible';
            });
        }
    });

    window.addEventListener('resize', function () {
        images.forEach(function (img) {
            if (img.complete && img.naturalWidth) {
                apply(img);
            }
        });
    });
})();

// Редактор форматированного текста в панели управления — заменяет
// собой textarea[data-rich-text] (RegionalFederation.intro_text/
// goals_text, Club.*_text, News.content) на contenteditable-поле с
// тулбаром: заголовок/подзаголовок, полужирный/курсив, выравнивание
// (включая по ширине), отступ абзаца.
// Исходная textarea не удаляется — только прячется (display: none,
// поэтому продолжает участвовать в отправке формы под тем же name) и
// на каждое изменение получает актуальный HTML из contenteditable.
// Само значение на сервере ещё раз чистится (routes/admin.py через
// richtext.sanitize_rich_text) — доверять тому, что пришло в
// POST-запросе, нельзя, даже если его собрал этот же редактор.
(function () {
    var textareas = document.querySelectorAll('textarea[data-rich-text]');
    if (!textareas.length) {
        return;
    }
    // Иначе Enter в contenteditable у части браузеров создаёт <div>
    // вместо <p> — с <p> предсказуемо работает и логика отступа/
    // выравнивания ниже (она берёт блоки — прямые дети редактора), и
    // серверная санитизация (richtext.py разрешает только p/h2/h3/br).
    document.execCommand('defaultParagraphSeparator', false, 'p');

    var INDENT_STEP = 40;
    var MAX_INDENT = 160;
    var HEADING_OPTIONS = [
        ['P', 'Обычный текст'],
        ['H2', 'Заголовок'],
        ['H3', 'Подзаголовок'],
    ];

    function escapeHtml(text) {
        var div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // Значение, сохранённое до появления этого редактора, — обычный
    // текст (в нём нет тегов) — оборачиваем в один абзац с <br> вместо
    // переносов строк, чтобы визуально осталось как было (переносы
    // строк, не пустые отступы между «абзацами»), но при этом контент
    // сразу стал понятной редактору структурой (блок, к которому можно
    // применить заголовок/выравнивание/отступ).
    function toEditableHtml(value) {
        if (!value) {
            // Не оставляем редактор совсем пустым (без единого блочного
            // элемента) — иначе первый же символ, набранный пользователем,
            // ложится прямо в контейнер редактора без обёртки <p>, и
            // execCommand('justifyFull')/formatBlock, встретив такое
            // выравнивание/заголовок позже, сами оборачивают текст в
            // блок не совсем чисто (Chromium попутно добавляет лишний
            // инлайновый style вроде font-size). Пустой абзац с самого
            // начала даёт предсказуемую структуру для всех команд тулбара.
            return '<p><br></p>';
        }
        if (/<[a-zA-Zа-яА-Я][^>]*>/.test(value)) {
            return value;
        }
        return '<p>' + value.split(/\r\n|\r|\n/).map(escapeHtml).join('<br>') + '</p>';
    }

    // Блоки (прямые дети редактора — p/h2/h3), затронутые текущим
    // выделением — к ним применяется отступ. Если по каким-то причинам
    // выделения нет (редактор ещё пуст, фокуса не было), откатываемся
    // на первый блок, чтобы кнопки не оказывались просто нерабочими.
    function selectedBlocks(editor) {
        var selection = window.getSelection();
        var blocks = [];
        if (selection.rangeCount) {
            var range = selection.getRangeAt(0);
            Array.prototype.forEach.call(editor.children, function (node) {
                if (range.intersectsNode(node)) {
                    blocks.push(node);
                }
            });
        }
        if (!blocks.length && editor.firstElementChild) {
            blocks.push(editor.firstElementChild);
        }
        return blocks;
    }

    function buildEditor(textarea) {
        var wrapper = document.createElement('div');
        wrapper.className = 'rich-text-editor';

        var toolbar = document.createElement('div');
        toolbar.className = 'rich-text-toolbar';

        var editor = document.createElement('div');
        editor.className = 'rich-text-editable form-control';
        editor.contentEditable = 'true';

        function sync() {
            // Пустой абзац-заглушка (см. toEditableHtml) не должен
            // притворяться сохранённым текстом — если пользователь ничего
            // не набрал (или стёр всё обратно), в textarea, а значит и в
            // БД, должна попасть пустая строка, а не «<p><br></p>»/пустые
            // теги, которые прошли бы проверку {% if поле %} в шаблонах
            // как заполненное значение.
            textarea.value = editor.textContent.trim() ? editor.innerHTML : '';
        }

        function toolbarAction(action) {
            editor.focus();
            action();
            sync();
        }

        var headingSelect = document.createElement('select');
        headingSelect.className = 'form-select form-select-sm rich-text-toolbar-select';
        headingSelect.title = 'Заголовок';
        HEADING_OPTIONS.forEach(function (item) {
            var option = document.createElement('option');
            option.value = item[0];
            option.textContent = item[1];
            headingSelect.appendChild(option);
        });
        headingSelect.addEventListener('mousedown', function () {
            // Клик по <select> сам по себе фокус с редактора не снимает
            // до открытия списка — без явного focus() тут execCommand
            // на change сработал бы уже без выделения в редакторе.
            editor.focus();
        });
        headingSelect.addEventListener('change', function () {
            toolbarAction(function () {
                document.execCommand('formatBlock', false, headingSelect.value);
            });
        });
        toolbar.appendChild(headingSelect);

        function addButton(label, title, action) {
            var button = document.createElement('button');
            button.type = 'button';
            button.className = 'btn btn-outline-secondary btn-sm';
            button.textContent = label;
            button.title = title;
            // mousedown, а не click: click срабатывает после mouseup,
            // к этому моменту contenteditable уже потерял выделение
            // текста (фокус ушёл на кнопку) — execCommand отработал бы
            // без выделения. preventDefault здесь же не даёт кнопке
            // забрать фокус у редактора.
            button.addEventListener('mousedown', function (event) {
                event.preventDefault();
                toolbarAction(action);
            });
            toolbar.appendChild(button);
            return button;
        }

        var boldButton = addButton('Ж', 'Полужирный', function () {
            document.execCommand('bold');
        });
        boldButton.style.fontWeight = 'bold';
        var italicButton = addButton('К', 'Курсив', function () {
            document.execCommand('italic');
        });
        italicButton.style.fontStyle = 'italic';

        addButton('По левому краю', 'Выравнивание по левому краю', function () {
            document.execCommand('justifyLeft');
        });
        addButton('По центру', 'Выравнивание по центру', function () {
            document.execCommand('justifyCenter');
        });
        addButton('По правому краю', 'Выравнивание по правому краю', function () {
            document.execCommand('justifyRight');
        });
        addButton('По ширине', 'Выравнивание по ширине', function () {
            document.execCommand('justifyFull');
        });
        addButton('Отступ −', 'Уменьшить отступ абзаца', function () {
            selectedBlocks(editor).forEach(function (block) {
                var current = parseInt(block.style.marginLeft, 10) || 0;
                var next = Math.max(0, current - INDENT_STEP);
                block.style.marginLeft = next ? next + 'px' : '';
            });
        });
        addButton('Отступ +', 'Увеличить отступ абзаца', function () {
            selectedBlocks(editor).forEach(function (block) {
                var current = parseInt(block.style.marginLeft, 10) || 0;
                var next = Math.min(MAX_INDENT, current + INDENT_STEP);
                block.style.marginLeft = next + 'px';
            });
        });

        editor.innerHTML = toEditableHtml(textarea.value);
        editor.addEventListener('input', sync);
        editor.addEventListener('blur', sync);
        sync();

        wrapper.appendChild(toolbar);
        wrapper.appendChild(editor);
        textarea.style.display = 'none';
        textarea.parentNode.insertBefore(wrapper, textarea);

        var form = textarea.closest('form');
        if (form) {
            // На случай, если ни одно событие редактора не долетело
            // (например, правку отменили сразу после фокуса) — перед
            // отправкой формы значение синхронизируется в любом случае.
            form.addEventListener('submit', sync);
        }
    }

    textareas.forEach(buildEditor);
})();

// Активация вкладки Bootstrap (data-bs-toggle="tab") по хэшу в адресе
// страницы при загрузке — сами вкладки переключаются по клику, но
// прямая ссылка с хэшем (например, "Отмена"/"К списку заявок" со
// страницы заявки на ЕКП обратно на #tab-forming) без этого всегда
// открывала бы первую вкладку, а не ту, что была в адресе.
(function () {
    if (!window.location.hash) {
        return;
    }
    var trigger;
    try {
        trigger = document.querySelector('[data-bs-toggle="tab"][data-bs-target="' + window.location.hash + '"]');
    } catch (e) {
        return;
    }
    if (trigger && window.bootstrap && window.bootstrap.Tab) {
        window.bootstrap.Tab.getOrCreateInstance(trigger).show();
    }
})();
