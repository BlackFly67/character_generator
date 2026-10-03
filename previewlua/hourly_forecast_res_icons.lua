local lvgl = require("lvgl")
local math = require("math")

--------------------------------------------------------------------------------
-- Модуль рендеринга текста из картинок-символов
--------------------------------------------------------------------------------
local TextImageRenderer = {}
TextImageRenderer.__index = TextImageRenderer

local function utf8_chars(str)
    return str:gmatch("[%z\1-\127\192-\247][\128-\191]*")
end

function TextImageRenderer.new(parent, config)
    local self = setmetatable({}, TextImageRenderer)
    self.parent = parent
    self.char_w = config.char_w or 24
    self.char_h = config.char_h or 26
    self.spacing = config.spacing or 0
    self.img_path = config.img_path or (SCRIPT_PATH or "/")
    self.char_map = config.char_map or {}
    self.char_advance = config.char_advance or {}
    self.img_opa = config.img_opa or 255
    self.images = {}
    return self
end

function TextImageRenderer:clear()
    for _, img in ipairs(self.images) do
        if img and img.delete then img:delete() end
    end
    self.images = {}
end

function TextImageRenderer:advanceFor(char)
    return self.char_advance[char] or self.char_w
end

function TextImageRenderer:render(text, x, y, align)
    self:clear()
    if not text or text == "" then return end

    align = align or "left"

    local char_list = {}
    for char in utf8_chars(text) do
        table.insert(char_list, char)
    end
    local char_count = #char_list
    if char_count == 0 then return end

    local total_w = (char_count - 1) * self.spacing
    for _, char in ipairs(char_list) do
        total_w = total_w + self:advanceFor(char)
    end

    local cur_x = x
    if align == "center" then
        cur_x = x - math.floor(total_w / 2)
    elseif align == "right" then
        cur_x = x - total_w
    end

    for _, char in ipairs(char_list) do
        if char ~= " " then
            local file_name = self.char_map[char]
            if file_name then
                local advance = self:advanceFor(char)
                local draw_x = cur_x - math.floor((self.char_w - advance) / 2)
                local img = lvgl.Image(self.parent, {
                    x = draw_x, y = y,
                    w = self.char_w, h = self.char_h,
                    src = self.img_path .. file_name,
                    bg_opa = lvgl.OPA(0),
                    img_opa = lvgl.OPA(self.img_opa)
                })
                img:add_flag(lvgl.FLAG.EVENT_BUBBLE)
                table.insert(self.images, img)
            end
        end
        cur_x = cur_x + self:advanceFor(char) + self.spacing
    end
end

--------------------------------------------------------------------------------
-- Чтение размера картинки из заголовка .bin (LVGL v8)
--------------------------------------------------------------------------------
local function getBinImageSize(path)
    local f = io.open(path, "rb")
    if not f then return nil, nil end
    local header = f:read(4)
    f:close()
    if not header or #header < 4 then return nil, nil end

    local b1, b2, b3, b4 = string.byte(header, 1, 4)
    local val = b1 + b2 * 256 + b3 * 65536 + b4 * 16777216

    local w = math.floor(val / 1024) % 2048
    local h = math.floor(val / 2097152) % 2048
    return w, h
end

--------------------------------------------------------------------------------
-- Извлечение иконок погоды напрямую из /system/image/weather.res
--
-- Формат записи: 4-байтный заголовок (cf|w|h, как и в обычных .bin) +
-- палитра 256 цветов BGRA (1024 байта) + w*h байт индексов в палитру.
--
-- Иконка читается из weather.res и перезаписывается заново КАЖДЫЙ РАЗ, когда
-- срабатывает renderForecast -- никакого персистентного кэша между запусками
-- нет. Временный файл пишется в собственную папку циферблата (SCRIPT_PATH), а
-- не в системные каталоги вроде /data/log -- и на каждый слот/строку
-- используется свой постоянный временный файл (перезаписывается), а не
-- отдельный файл на каждый код погоды.
--------------------------------------------------------------------------------
local WEATHER_RES_PATH = "/system/image/weather.res"
local WEATHER_RES_ICON_W = 48
local WEATHER_RES_ICON_H = 48
local WEATHER_RES_PALETTE_SIZE = 1024

local WEATHER_RES_TMP_PREFIX = "_wx_tmp_row"

-- true  = копируем блок (заголовок+палитра+индексы) из weather.res КАК ЕСТЬ,
--         в исходном формате cf=10 (LV_IMG_CF_INDEXED_8BIT) -- без конвертации.
--         Проще и быстрее, но ТРЕБУЕТ, чтобы lvgl.Image в этом движке скриптов
--         умел открывать indexed-8bit картинки.
-- false = конвертируем indexed-8bit -> BGRA8888 (cf=5) -- заведомо рабочий,
--         но более медленный вариант (цикл по пикселям в Lua).
local WEATHER_RES_RAW_COPY = true

-- код явления (как в API/приложении «Погода») -> смещение начала записи
-- (4-байтного заголовка) этой иконки внутри weather.res
local WEATHER_RES_OFFSETS = {
    [0]  = 145452,    -- Ясно
    [1]  = 1996927,   -- Облачно
    [2]  = 1592959,   -- Пасмурно
    [4]  = 2567425,   -- Гроза с дождём
    [5]  = 2328285,   -- Гроза с градом
    [6]  = 2366017,   -- Дождь со снегом
    [7]  = 2564093,   -- Небольшой дождь
    [8]  = 2291913,   -- Умеренный дождь
    [9]  = 2152530,   -- Сильный дождь
    [14] = 2360825,   -- Небольшой снег
    [15] = 2377805,   -- Умеренный снег
    [16] = 326219,    -- Сильный снегопад
    [18] = 2357493,   -- Туман
    [19] = 1042215,   -- Ледяной дождь
    [20] = 1530471,   -- Песчаная буря
    [29] = 1925067,   -- Пыль
    [53] = 142120,    -- Смог
    [99] = 2374473,   -- Неизвестно
}

-- коды без отдельной иконки в weather.res -- переиспользуют ближайший похожий код
local WEATHER_CODE_ALIAS = {
    [3]  = 7,   [10] = 9,   [11] = 9,  [12] = 9,  [13] = 14,
    [17] = 16,  [21] = 7,   [22] = 8,  [23] = 9,  [24] = 9,
    [25] = 9,   [26] = 14,  [27] = 15, [28] = 16, [30] = 29,
    [31] = 20,  [32] = 99,  [33] = 99, [34] = 99, [35] = 18,
}

local DEFAULT_WEATHER_CODE = 99

local function resolveWeatherCode(code)
    if WEATHER_RES_OFFSETS[code] then return code end
    local alias = WEATHER_CODE_ALIAS[code]
    if alias and WEATHER_RES_OFFSETS[alias] then return alias end
    return DEFAULT_WEATHER_CODE
end

-- Читает иконку для кода `code` прямо из weather.res и пишет её во временный
-- файл `out_path` (один файл на СЛОТ/строку; перезаписывается при каждом вызове)
local function extractWeatherIcon(code, out_path)
    local offset = WEATHER_RES_OFFSETS[code]
    if not offset then return nil end

    local src = io.open(WEATHER_RES_PATH, "rb")
    if not src then return nil end

    local body_len = WEATHER_RES_PALETTE_SIZE + WEATHER_RES_ICON_W * WEATHER_RES_ICON_H

    if WEATHER_RES_RAW_COPY then
        src:seek("set", offset)
        local blob = src:read(4 + body_len)
        src:close()
        if not blob or #blob < 4 + body_len then return nil end

        local out = io.open(out_path, "wb")
        if not out then return nil end
        out:write(blob)
        out:close()

        return out_path
    end

    -- Запасной вариант: конвертация indexed-8bit -> BGRA8888 (cf=5)
    src:seek("set", offset + 4)
    local raw = src:read(body_len)
    src:close()
    if not raw or #raw < body_len then
        return nil
    end

    local palette = raw:sub(1, WEATHER_RES_PALETTE_SIZE)
    local indices = raw:sub(WEATHER_RES_PALETTE_SIZE + 1)

    -- Заголовок нашего обычного .bin: cf=5, w, h
    -- val = cf + (w << 10) + (h << 21)
    local cf = 5
    local val = cf + WEATHER_RES_ICON_W * 1024 + WEATHER_RES_ICON_H * 2097152
    local header = string.char(
        val % 256,
        math.floor(val / 256) % 256,
        math.floor(val / 65536) % 256,
        math.floor(val / 16777216) % 256
    )

    local out = io.open(out_path, "wb")
    if not out then return nil end
    out:write(header)

    local buf = {}
    local n = WEATHER_RES_ICON_W * WEATHER_RES_ICON_H
    for i = 1, n do
        local idx = string.byte(indices, i)
        local p = idx * 4
        buf[i] = palette:sub(p + 1, p + 4)
    end
    out:write(table.concat(buf))
    out:close()

    return out_path
end

--------------------------------------------------------------------------------
-- Основной скрипт
--------------------------------------------------------------------------------
local function entry()
    local global_w = 200 --lvgl.HOR_RES()
    local global_h = 150 --lvgl.VER_RES()

    local root = lvgl.Object(nil, {
        w = global_w, h = global_h,
        bg_color = 0, bg_opa = lvgl.OPA(0),
        border_width = 0,
        pad_all = 0
    })
    root:clear_flag(lvgl.FLAG.SCROLLABLE)
    root:add_flag(lvgl.FLAG.EVENT_BUBBLE)

    local IMAGE_PATH = SCRIPT_PATH or "/"

    --------------------------------------------------------------------------
    -- Настройки блока
    --------------------------------------------------------------------------
    local HOURS_VISIBLE = 4
    local DAYS_VISIBLE  = 4
    local ALIGN         = "center"
    local TIME_OPACITY  = 140

    -- Иконки погоды всегда 48x48 из weather.res
    local ICON_W, ICON_H = WEATHER_RES_ICON_W, WEATHER_RES_ICON_H

    -- Обычные цифры (для температуры в почасовом)
    local DIGIT_W, DIGIT_H = getBinImageSize(IMAGE_PATH .. "num_01.bin")
    DIGIT_W = DIGIT_W or 30
    DIGIT_H = DIGIT_H or 37

    -- Уменьшенные цифры (для времени)
    local TIME_DIGIT_W, TIME_DIGIT_H = getBinImageSize(IMAGE_PATH .. "num_small_01.bin")
    local using_small_time_digits = TIME_DIGIT_W ~= nil
    TIME_DIGIT_W = TIME_DIGIT_W or DIGIT_W
    TIME_DIGIT_H = TIME_DIGIT_H or DIGIT_H

    -- Средние цифры (для температуры в дневном режиме) -- 19x36 по ТЗ
    local MED_DIGIT_W = 19
    local MED_DIGIT_H = 36

    -- Картинки дней недели -- 63x39 по ТЗ
    local WD_W = 63
    local WD_H = 39

    local narrow_advance_temp = {
        [":"] = math.floor(DIGIT_W / 2),
        ["°"] = math.floor(DIGIT_W / 2),
    }
    local narrow_advance_time = {
        [":"] = math.floor(TIME_DIGIT_W / 2),
        ["°"] = math.floor(TIME_DIGIT_W / 2),
    }
    local narrow_advance_med = {
        ["/"] = math.floor(MED_DIGIT_W * 0.6),
        ["°"] = math.floor(MED_DIGIT_W * 0.7),
    }

    local TIME_SLOT_W = TIME_DIGIT_W * 5 + 5
    local ICON_SLOT_W = ICON_W - 6
    local TEMP_SLOT_W = DIGIT_W * 3

    local ROW_WIDTH  = TIME_SLOT_W + ICON_SLOT_W + TEMP_SLOT_W
    local ROW_HEIGHT = math.max(DIGIT_H, ICON_H) - 9

    local BLOCK_X
    if ALIGN == "center" then
        BLOCK_X = math.floor((global_w - ROW_WIDTH) / 2)
    elseif ALIGN == "right" then
        BLOCK_X = global_w - ROW_WIDTH
    else
        BLOCK_X = 0
    end
    local BLOCK_Y = 0

    local TIME_SLOT_CENTER_X = BLOCK_X + math.floor(TIME_SLOT_W / 2) - 10
    local ICON_SLOT_CENTER_X = BLOCK_X + TIME_SLOT_W + math.floor(ICON_SLOT_W / 2) - 12
    local TEMP_SLOT_CENTER_X = BLOCK_X + TIME_SLOT_W + ICON_SLOT_W + math.floor(TEMP_SLOT_W / 2)

    --------------------------------------------------------------------------
    -- Карта цифр
    --------------------------------------------------------------------------
    local digits = {
        "0", "1", "2", "3", "4", "5", "6", "7", "8", "9", ":", "-", "°"
    }
    local digit_map = {}
    local digit_map_small = {}
    for idx, ch in ipairs(digits) do
        digit_map[ch] = string.format("num_%02d.bin", idx)
        digit_map_small[ch] = string.format("num_small_%02d.bin", idx)
    end

    -- num_med_: 0 1 2 3 4 5 6 7 8 9 - ° /
    local med_digits = {
        "0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "-", "°", "/"
    }
    local med_map = {}
    for idx, ch in ipairs(med_digits) do
        med_map[ch] = string.format("num_med_%02d.bin", idx)
    end

    --------------------------------------------------------------------------
    -- Рендереры
    --------------------------------------------------------------------------
    local time_renderers = {}
    local temp_renderers = {}
    for row = 1, HOURS_VISIBLE do
        time_renderers[row] = TextImageRenderer.new(root, {
            char_w = TIME_DIGIT_W, char_h = TIME_DIGIT_H, spacing = -4,
            img_path = IMAGE_PATH,
            char_map = using_small_time_digits and digit_map_small or digit_map,
            char_advance = narrow_advance_time,
            img_opa = TIME_OPACITY
        })
        temp_renderers[row] = TextImageRenderer.new(root, {
            char_w = DIGIT_W, char_h = DIGIT_H, spacing = -6,
            img_path = IMAGE_PATH, char_map = digit_map,
            char_advance = narrow_advance_temp
        })
    end

    -- Отдельный рендерер для температуры в дневном режиме (num_med_*)
    local med_temp_renderers = {}
    for row = 1, DAYS_VISIBLE do
        med_temp_renderers[row] = TextImageRenderer.new(root, {
            char_w = MED_DIGIT_W, char_h = MED_DIGIT_H, spacing = -6,
            img_path = IMAGE_PATH, char_map = med_map,
            char_advance = narrow_advance_med
        })
    end

    -- Объекты под иконки дней недели (wd_*.bin) -- по одному на строку
    local weekday_widgets = {}
    for row = 1, DAYS_VISIBLE do
        weekday_widgets[row] = lvgl.Image(root, {
            x = 0, y = 0,
            w = WD_W, h = WD_H,
            src = IMAGE_PATH .. "wd_01.bin",
            bg_opa = lvgl.OPA(0)
        })
        weekday_widgets[row]:add_flag(lvgl.FLAG.EVENT_BUBBLE)
    end

    --------------------------------------------------------------------------
    -- Иконки погоды: извлекаются из /system/image/weather.res во временные
    -- .bin-файлы (по одному на строку), без отдельных weatherXX.bin.
    --------------------------------------------------------------------------
    local icon_widgets = {}
    local icon_tmp_paths = {}
    for row = 1, HOURS_VISIBLE do
        icon_tmp_paths[row] = IMAGE_PATH .. WEATHER_RES_TMP_PREFIX .. row .. ".bin"
        local first_src = extractWeatherIcon(DEFAULT_WEATHER_CODE, icon_tmp_paths[row])
        icon_widgets[row] = lvgl.Image(root, {
            x = 0, y = 0,
            w = ICON_W, h = ICON_H,
            src = first_src,
            bg_opa = lvgl.OPA(0)
        })
        icon_widgets[row]:add_flag(lvgl.FLAG.EVENT_BUBBLE)
    end

    --------------------------------------------------------------------------
    -- Чтение данных из wdata2
    --------------------------------------------------------------------------
    local REC0_OFFSET   = 990
    local REC_STRIDE    = 48
    local REC_COUNT     = 23
    local DAILY0_OFFSET = 388
    local DAILY_STRIDE  = 24
    local DAILY_COUNT   = 5

    local function readInt8(rec, byteOffset)
        local v = string.byte(rec, byteOffset + 1)
        if v >= 128 then v = v - 256 end
        return v
    end

    local function getCurrentDateParts(content, pos)
        local ts = content:sub(pos + 6, pos + 6 + 19)
        local y  = tonumber(ts:sub(1, 4))
        local mo = tonumber(ts:sub(6, 7))
        local d  = tonumber(ts:sub(9, 10))
        local hh = tonumber(ts:sub(12, 13))
        return y, mo, d, hh
    end

    local function getHourlyForecast(count)
        local result = {}
        local f = io.open("/data/app/weather/database.db", "rb")
        if not f then return result end
        local content = f:read("*a")
        f:close()
        if not content then return result end

        local pos = content:find("wdata2", 1, true)
        if not pos then return result end

        local _, _, _, base_hour = getCurrentDateParts(content, pos)
        base_hour = base_hour or 0

        for i = 1, math.min(count, REC_COUNT - 1) do
            local rec_start = pos + REC0_OFFSET + REC_STRIDE * i
            local rec = content:sub(rec_start, rec_start + 47)
            if #rec == 48 then
                local icon_code = readInt8(rec, 22)
                local temp      = readInt8(rec, 26)
                local hour = (base_hour + i) % 24
                table.insert(result, { hour = hour, temp = temp, icon_code = icon_code })
            end
        end
        return result
    end

    local function getDailyForecast(count)
        local result = {}
        local f = io.open("/data/app/weather/database.db", "rb")
        if not f then return result end
        local content = f:read("*a")
        f:close()
        if not content then return result end

        local pos = content:find("wdata2", 1, true)
        if not pos then return result end

        local y, mo, d, _ = getCurrentDateParts(content, pos)
        if not y or not mo or not d then return result end

        local base_t = os.time({ year = y, month = mo, day = d, hour = 12 })

        for i = 0, math.min(count, DAILY_COUNT) - 1 do
            local rec_start = pos + DAILY0_OFFSET + DAILY_STRIDE * i
            local rec = content:sub(rec_start, rec_start + DAILY_STRIDE - 1)
            if #rec == DAILY_STRIDE then
                local day_icon   = readInt8(rec, 0)
                local night_icon = readInt8(rec, 2)
                local high       = readInt8(rec, 4)
                local low        = readInt8(rec, 6)

                local day_t = base_t + i * 86400
                -- wday: 1=Вс, 2=Пн, 3=Вт, 4=Ср, 5=Чт, 6=Пт, 7=Сб
                local wday = os.date("*t", day_t).wday
                local wd_file = string.format("wd_%02d.bin", wday)

                table.insert(result, {
                    wd_file   = wd_file,
                    day_icon  = day_icon,
                    high      = high,
                    low       = low,
                })
            end
        end
        return result
    end

    --------------------------------------------------------------------------
    -- Рендер
    --------------------------------------------------------------------------
    local forecast_mode = "hourly"

    local function formatTime(hour)
        return string.format("%02d:00", hour)
    end

    local function formatTemp(temp)
        return string.format("%d°", temp)
    end

    local function renderHourly()
        -- скрыть дни недели
        for row = 1, DAYS_VISIBLE do
            weekday_widgets[row]:add_flag(lvgl.FLAG.HIDDEN)
        end
        for row = 1, DAYS_VISIBLE do
            med_temp_renderers[row]:clear()
        end

        local data = getHourlyForecast(HOURS_VISIBLE)

        for row = 1, HOURS_VISIBLE do
            local item = data[row]
            local row_y = BLOCK_Y + (row - 1) * ROW_HEIGHT
            local row_center_y = row_y + math.floor(ROW_HEIGHT / 2)
            local time_text_y = row_center_y - math.floor(TIME_DIGIT_H / 2)
            local temp_text_y = row_center_y - math.floor(DIGIT_H / 2)

            if item then
                time_renderers[row]:render(formatTime(item.hour), TIME_SLOT_CENTER_X, time_text_y, "center")
                temp_renderers[row]:render(formatTemp(item.temp), TEMP_SLOT_CENTER_X, temp_text_y, "center")

                -- иконка читается из weather.res и перезаписывается в файл
                -- этого слота ЗАНОВО при каждом срабатывании -- без кэша
                local resolved_code = resolveWeatherCode(item.icon_code)
                local icon_path = extractWeatherIcon(resolved_code, icon_tmp_paths[row])
                    or extractWeatherIcon(DEFAULT_WEATHER_CODE, icon_tmp_paths[row])
                local icon_x = ICON_SLOT_CENTER_X - math.floor(ICON_W / 2)
                local icon_y = row_center_y - math.floor(ICON_H / 2)
                icon_widgets[row]:set({
                    x = icon_x, y = icon_y,
                    src = icon_path
                })
                icon_widgets[row]:clear_flag(lvgl.FLAG.HIDDEN)
            else
                time_renderers[row]:clear()
                temp_renderers[row]:clear()
                icon_widgets[row]:add_flag(lvgl.FLAG.HIDDEN)
            end
        end
    end

    local function renderDaily()
        -- скрыть почасовые рендереры времени и температуры
        for row = 1, HOURS_VISIBLE do
            time_renderers[row]:clear()
            temp_renderers[row]:clear()
        end

        local data = getDailyForecast(DAYS_VISIBLE)

        for row = 1, DAYS_VISIBLE do
            local item = data[row]
            local row_y = BLOCK_Y + (row - 1) * ROW_HEIGHT
            local row_center_y = row_y + math.floor(ROW_HEIGHT / 2)
            local temp_text_y = row_center_y - math.floor(MED_DIGIT_H / 2)
            local wd_y = row_center_y - math.floor(WD_H / 2)

            if item then
                -- день недели -- одной картинкой
                local wd_x = TIME_SLOT_CENTER_X - math.floor(WD_W / 2)
                weekday_widgets[row]:set({
                    x = wd_x, y = wd_y,
                    src = IMAGE_PATH .. item.wd_file
                })
                weekday_widgets[row]:clear_flag(lvgl.FLAG.HIDDEN)

                -- high°/low°
                local temp_text = string.format("%d°/%d°", item.high, item.low)
                med_temp_renderers[row]:render(temp_text, TEMP_SLOT_CENTER_X, temp_text_y, "center")

                -- иконка из weather.res
                local resolved_code = resolveWeatherCode(item.day_icon)
                local icon_path = extractWeatherIcon(resolved_code, icon_tmp_paths[row])
                    or extractWeatherIcon(DEFAULT_WEATHER_CODE, icon_tmp_paths[row])
                local icon_x = ICON_SLOT_CENTER_X - math.floor(ICON_W / 2)
                local icon_y = row_center_y - math.floor(ICON_H / 2)
                icon_widgets[row]:set({
                    x = icon_x, y = icon_y,
                    src = icon_path
                })
                icon_widgets[row]:clear_flag(lvgl.FLAG.HIDDEN)
            else
                weekday_widgets[row]:add_flag(lvgl.FLAG.HIDDEN)
                med_temp_renderers[row]:clear()
                icon_widgets[row]:add_flag(lvgl.FLAG.HIDDEN)
            end
        end

        -- скрыть лишние почасовые строки, если дней меньше, чем часов
        for row = DAYS_VISIBLE + 1, HOURS_VISIBLE do
            icon_widgets[row]:add_flag(lvgl.FLAG.HIDDEN)
        end
    end

    local function renderForecast()
        if forecast_mode == "hourly" then
            renderHourly()
        else
            renderDaily()
        end
    end

    renderForecast()

    --------------------------------------------------------------------------
    -- Обработчик тапа
    --------------------------------------------------------------------------
    local click_area = lvgl.Object(root, {
        x = BLOCK_X,
        y = BLOCK_Y,
        w = ROW_WIDTH,
        h = ROW_HEIGHT * HOURS_VISIBLE,
        bg_opa = lvgl.OPA(0),
        border_width = 0,
        pad_all = 0
    })
    click_area:add_flag(lvgl.FLAG.CLICKABLE)

    click_area:onevent(lvgl.EVENT.CLICKED, function()
        if forecast_mode == "hourly" then
            forecast_mode = "daily"
        else
            forecast_mode = "hourly"
        end
        renderForecast()
    end)

    --------------------------------------------------------------------------
    local forecast_timer = lvgl.Timer({
        period = 900000,
        repeat_count = -1,
        cb = function(timer)
            renderForecast()
        end
    })

    local function screenONCb()
        renderForecast()
    end
    local function screenOFFCb() end

    return screenONCb, screenOFFCb
end

local onCb, offCb = entry()

function ScreenStateChangedCB(pre, now, reason)
    if pre ~= "ON" and now == "ON" then
        if onCb then onCb() end
    elseif pre == "ON" and now ~= "ON" then
        if offCb then offCb() end
    end
end