local lvgl = require("lvgl")
local math = require("math")

--------------------------------------------------------------------------------
-- Чтение int8 (со знаком)
--------------------------------------------------------------------------------
local function readInt8(rec, byteOffset)
    local v = string.byte(rec, byteOffset + 1)
    if v >= 128 then v = v - 256 end
    return v
end

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
                    bg_opa = lvgl.OPA(0)
                })
                img:add_flag(lvgl.FLAG.EVENT_BUBBLE)
                table.insert(self.images, img)
            end
        end
        cur_x = cur_x + self:advanceFor(char) + self.spacing
    end
end

--------------------------------------------------------------------------------
-- Чтение размера .bin (LVGL v8)
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
-- Чтение всех данных из database.db
--------------------------------------------------------------------------------
local DB_PATH = "/data/app/weather/database.db"

local function readFloat32LE(s, i)
    local b1, b2, b3, b4 = string.byte(s, i, i + 3)
    if not b1 then return 0 end
    -- распаковка IEEE 754 float32
    local sign = (b4 >= 128) and -1 or 1
    local exp = ((b4 % 128) * 2) + math.floor(b3 / 128)
    local mant = ((b3 % 128) * 65536) + b2 * 256 + b1
    if exp == 0 and mant == 0 then return 0 end
    if exp == 0 then
        return sign * (mant / 8388608) * math.pow(2, -126)
    elseif exp == 255 then
        return sign * math.huge
    else
        return sign * (1 + mant / 8388608) * math.pow(2, exp - 127)
    end
end

local function readInt16LE(s, i)
    local lo, hi = string.byte(s, i, i + 1)
    if not lo then return 0 end
    local v = lo + hi * 256
    if v >= 32768 then v = v - 65536 end
    return v
end

local function readUtf8String(s, i)
    local j = i
    while j <= #s do
        if string.byte(s, j) == 0 then break end
        j = j + 1
    end
    return s:sub(i, j - 1)
end

local function parseDate(date_str)
    -- "YYYY-MM-DDTHH:MM:SS+HH:MM"
    local y = tonumber(date_str:sub(1, 4))
    local m = tonumber(date_str:sub(6, 7))
    local d = tonumber(date_str:sub(9, 10))
    local hh = tonumber(date_str:sub(12, 13))
    local mm = tonumber(date_str:sub(15, 16))
    local ss = tonumber(date_str:sub(18, 19))
    return y, m, d, hh, mm, ss
end

local function getWeatherData()
    local result = {
        city = "Не определено",
        pressure = 0,
        icon = 0,
        temp = 0,
        humidity = 0,
        uv = 0,
        wind_dir = 0,
        wind_level = 0,
        aqi = 0,
        sunrise_h = 6, sunrise_m = 0,
        sunset_h = 18, sunset_m = 0,
        air_text = "",
        base_hour = 0,
        base_y = 2000, base_m = 1, base_d = 1,
        daily = {},
        hourly = {},
    }

    local f = io.open(DB_PATH, "rb")
    if not f then return result end
    local content = f:read("*a")
    f:close()
    if not content then return result end

    local pos = content:find("wdata2", 1, true)
    if not pos then return result end

    -- Дата
    local date_str = content:sub(pos + 6, pos + 6 + 24)
    local y, m, d, hh, mm, ss = parseDate(date_str)
    result.base_y, result.base_m, result.base_d = y or 2000, m or 1, d or 1
    result.base_hour = hh or 0

    -- Город
    result.city = readUtf8String(content, pos + 31)

    -- Текущая погода
    result.pressure   = readFloat32LE(content, pos + 202)
    result.icon       = readInt8(content, pos + 206)
    result.temp       = readInt8(content, pos + 208)
    result.humidity   = readInt8(content, pos + 210)
    result.uv         = readInt8(content, pos + 212)
    result.wind_dir   = readInt16LE(content, pos + 214)
    result.wind_level = readInt8(content, pos + 216)
    result.aqi        = readInt8(content, pos + 218)
    result.sunrise_h  = readInt8(content, pos + 220)
    result.sunrise_m  = readInt8(content, pos + 221)
    result.sunset_h   = readInt8(content, pos + 222)
    result.sunset_m   = readInt8(content, pos + 223)
    result.air_text   = readUtf8String(content, pos + 224)

    -- Дневной прогноз
    local daily0_offset = 388
    local daily_stride = 24
    for dd = 0, 4 do
        local rec_start = pos + daily0_offset + daily_stride * dd
        local rec = content:sub(rec_start, rec_start + daily_stride - 1)
        if #rec == daily_stride then
            table.insert(result.daily, {
                day_icon   = readInt8(rec, 0),
                night_icon = readInt8(rec, 2),
                high       = readInt8(rec, 4),
                low        = readInt8(rec, 6),
            })
        end
    end

    -- Почасовой прогноз
    local hourly0_offset = 990
    local hourly_stride = 48
    local hourly_count = readInt16LE(content, pos + hourly0_offset)
    if hourly_count > 23 then hourly_count = 23 end

    for h = 1, hourly_count do
        local rec_start = pos + hourly0_offset + 2 + hourly_stride * (h - 1)
        local rec = content:sub(rec_start, rec_start + hourly_stride - 1)
        if #rec == hourly_stride then
            table.insert(result.hourly, {
                aqi  = readInt16LE(rec, 0),
                text = readUtf8String(rec, 2),
                icon = readInt8(rec, 22),
                temp = readInt8(rec, 26),
                hour = (result.base_hour + h) % 24,
            })
        end
    end

    return result
end

--------------------------------------------------------------------------------
-- Основной скрипт
--------------------------------------------------------------------------------
local function entry()
    local global_w = lvgl.HOR_RES()
    local global_h = lvgl.VER_RES()

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
    -- Настройки вывода
    --------------------------------------------------------------------------
    local HOURS_VISIBLE = 4
    local DAYS_VISIBLE  = 5
    local ALIGN         = "center"

    local ICON_W, ICON_H = getBinImageSize(IMAGE_PATH .. "weather00.bin")
    ICON_W = ICON_W or 50
    ICON_H = ICON_H or 50

    local DIGIT_W, DIGIT_H = getBinImageSize(IMAGE_PATH .. "num_01.bin")
    DIGIT_W = DIGIT_W or 30
    DIGIT_H = DIGIT_H or 37

    local narrow_advance = {
        [":"] = math.floor(DIGIT_W / 2),
        ["°"] = math.floor(DIGIT_W / 2),
    }

    -- Общий блок
    local BLOCK_WIDTH  = 400
    local BLOCK_X      = math.floor((global_w - BLOCK_WIDTH) / 2)
    local BLOCK_Y      = 0

    -- Блок текущей погоды (верхний)
    local NOW_X        = BLOCK_X
    local NOW_Y        = BLOCK_Y
    local NOW_ICON_X   = NOW_X + 5
    local NOW_ICON_Y   = NOW_Y + 5
    local NOW_TEMP_X   = NOW_X + 70
    local NOW_TEMP_Y   = NOW_Y + 5
    local NOW_CITY_Y   = NOW_Y + 55
    local NOW_DETAIL_Y = NOW_Y + 90
    local NOW_DETAIL2_Y = NOW_Y + 115

    -- Блок почасового прогноза
    local HOURS_Y      = BLOCK_Y + 160
    local HOUR_COL_W   = 90
    local HOURS_X      = BLOCK_X
    local HOUR_TIME_Y  = HOURS_Y
    local HOUR_ICON_Y  = HOURS_Y + 30
    local HOUR_TEMP_Y  = HOURS_Y + 85

    -- Блок дневного прогноза
    local DAYS_Y       = BLOCK_Y + 280
    local DAY_COL_W    = 80
    local DAYS_X       = BLOCK_X
    local DAY_ICON_Y   = DAYS_Y
    local DAY_HIGH_Y   = DAYS_Y + 55
    local DAY_LOW_Y    = DAYS_Y + 85

    --------------------------------------------------------------------------
    -- Символы
    --------------------------------------------------------------------------
    -- Кириллица + латиница
    local letters = {
        "А", "Б", "В", "Г", "Д", "Е", "Ё", "Ж", "З", "И", "Й", "К", "Л", "М", "Н", "О", "П", "Р", "С", "Т", "У", "Ф", "Х", "Ц", "Ч", "Ш", "Щ", "Ы", "Э", "Ю", "Я",
        "а", "б", "в", "г", "д", "е", "ё", "ж", "з", "и", "й", "к", "л", "м", "н", "о", "п", "р", "с", "т", "у", "ф", "х", "ц", "ч", "ш", "щ", "ъ", "ы", "ь", "э", "ю", "я",
        "-",
        "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z",
        "a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l", "m", "n", "o", "p", "q", "r", "s", "t", "u", "v", "w", "x", "y", "z",
        " ",
    }
    local symb_map = {}
    for idx, ch in ipairs(letters) do
        symb_map[ch] = string.format("symb_%02d.bin", idx)
    end

    -- Цифры + знаки
    local digits = {
        "0", "1", "2", "3", "4", "5", "6", "7", "8", "9", ":", "-", "°"
    }
    local digit_map = {}
    for idx, ch in ipairs(digits) do
        digit_map[ch] = string.format("num_%02d.bin", idx)
    end

    --------------------------------------------------------------------------
    -- Иконки погоды
    --------------------------------------------------------------------------
    local weather_icons = {
        [0]  = "weather00.bin",
        [1]  = "weather01.bin",
        [2]  = "weather02.bin",
        [3]  = "weather07.bin",
        [4]  = "weather04.bin",
        [5]  = "weather05.bin",
        [6]  = "weather06.bin",
        [7]  = "weather07.bin",
        [8]  = "weather08.bin",
        [9]  = "weather09.bin",
        [10] = "weather09.bin",
        [13] = "weather13.bin",
        [14] = "weather13.bin",
        [15] = "weather15.bin",
        [16] = "weather16.bin",
        [17] = "weather16.bin",
        [18] = "weather18.bin",
        [19] = "weather19.bin",
        [20] = "weather20.bin",
        [29] = "weather29.bin",
        [35] = "weather18.bin",
        [53] = "weather53.bin",
    }
    local DEFAULT_ICON = "weather99.bin"

    --------------------------------------------------------------------------
    -- Рендереры
    --------------------------------------------------------------------------
    -- Буквы (город, детали)
    local city_renderer = TextImageRenderer.new(root, {
        char_w = 24, char_h = 26, spacing = -6,
        img_path = IMAGE_PATH, char_map = symb_map
    })
    local detail_renderer = TextImageRenderer.new(root, {
        char_w = 24, char_h = 26, spacing = -6,
        img_path = IMAGE_PATH, char_map = symb_map
    })

    -- Цифры (температура, время)
    local big_temp_renderer = TextImageRenderer.new(root, {
        char_w = DIGIT_W, char_h = DIGIT_H, spacing = -4,
        img_path = IMAGE_PATH, char_map = digit_map,
        char_advance = narrow_advance
    })

    local hour_time_renderers = {}
    local hour_temp_renderers = {}
    for col = 1, HOURS_VISIBLE do
        hour_time_renderers[col] = TextImageRenderer.new(root, {
            char_w = DIGIT_W, char_h = DIGIT_H, spacing = -4,
            img_path = IMAGE_PATH, char_map = digit_map,
            char_advance = narrow_advance
        })
        hour_temp_renderers[col] = TextImageRenderer.new(root, {
            char_w = DIGIT_W, char_h = DIGIT_H, spacing = -4,
            img_path = IMAGE_PATH, char_map = digit_map,
            char_advance = narrow_advance
        })
    end

    local day_high_renderers = {}
    local day_low_renderers = {}
    for col = 1, DAYS_VISIBLE do
        day_high_renderers[col] = TextImageRenderer.new(root, {
            char_w = DIGIT_W, char_h = DIGIT_H, spacing = -4,
            img_path = IMAGE_PATH, char_map = digit_map,
            char_advance = narrow_advance
        })
        day_low_renderers[col] = TextImageRenderer.new(root, {
            char_w = DIGIT_W, char_h = DIGIT_H, spacing = -4,
            img_path = IMAGE_PATH, char_map = digit_map,
            char_advance = narrow_advance
        })
    end

    -- Иконки
    local now_icon = lvgl.Image(root, {
        x = NOW_ICON_X, y = NOW_ICON_Y,
        w = ICON_W, h = ICON_H,
        src = IMAGE_PATH .. DEFAULT_ICON,
        bg_opa = lvgl.OPA(0)
    })
    now_icon:add_flag(lvgl.FLAG.EVENT_BUBBLE)

    local hour_icons = {}
    for col = 1, HOURS_VISIBLE do
        hour_icons[col] = lvgl.Image(root, {
            x = 0, y = 0, w = ICON_W, h = ICON_H,
            src = IMAGE_PATH .. DEFAULT_ICON,
            bg_opa = lvgl.OPA(0)
        })
        hour_icons[col]:add_flag(lvgl.FLAG.EVENT_BUBBLE)
    end

    local day_icons = {}
    for col = 1, DAYS_VISIBLE do
        day_icons[col] = lvgl.Image(root, {
            x = 0, y = 0, w = ICON_W, h = ICON_H,
            src = IMAGE_PATH .. DEFAULT_ICON,
            bg_opa = lvgl.OPA(0)
        })
        day_icons[col]:add_flag(lvgl.FLAG.EVENT_BUBBLE)
    end

    --------------------------------------------------------------------------
    -- Отрисовка
    --------------------------------------------------------------------------
    local function setIcon(widget, code)
        local file = weather_icons[code] or DEFAULT_ICON
        widget:set({ src = IMAGE_PATH .. file })
    end

    local function renderAll()
        local data = getWeatherData()

        -- === Текущая погода ===
        -- Иконка
        setIcon(now_icon, data.icon)
        now_icon:set({ x = NOW_ICON_X, y = NOW_ICON_Y })

        -- Температура (большая)
        big_temp_renderer:render(string.format("%d°", data.temp), NOW_TEMP_X, NOW_TEMP_Y, "left")

        -- Город
        city_renderer:render(data.city, NOW_X, NOW_CITY_Y, "left")

        -- Детали: влажность, ветер, UV, давление
        detail_renderer:render(
            string.format("Влажн: %d%%  UV: %d  AQI: %d", data.humidity, data.uv, data.aqi),
            NOW_X, NOW_DETAIL_Y, "left"
        )
        detail_renderer:render(
            string.format("Давл: %d hPa", math.floor(data.pressure / 100 + 0.5)),
            NOW_X, NOW_DETAIL2_Y, "left"
        )

        -- === Почасовой прогноз (4 колонки) ===
        for col = 1, HOURS_VISIBLE do
            local item = data.hourly[col]
            local col_x = HOURS_X + (col - 1) * HOUR_COL_W
            local col_center = col_x + math.floor(HOUR_COL_W / 2)

            if item then
                hour_time_renderers[col]:render(
                    string.format("%02d:00", item.hour),
                    col_center, HOUR_TIME_Y, "center"
                )
                hour_temp_renderers[col]:render(
                    string.format("%d°", item.temp),
                    col_center, HOUR_TEMP_Y, "center"
                )
                setIcon(hour_icons[col], item.icon)
                hour_icons[col]:set({
                    x = col_center - math.floor(ICON_W / 2),
                    y = HOUR_ICON_Y
                })
                hour_icons[col]:clear_flag(lvgl.FLAG.HIDDEN)
            else
                hour_time_renderers[col]:clear()
                hour_temp_renderers[col]:clear()
                hour_icons[col]:add_flag(lvgl.FLAG.HIDDEN)
            end
        end

        -- === Дневной прогноз (5 колонок) ===
        for col = 1, DAYS_VISIBLE do
            local item = data.daily[col]
            local col_x = DAYS_X + (col - 1) * DAY_COL_W
            local col_center = col_x + math.floor(DAY_COL_W / 2)

            if item then
                day_high_renderers[col]:render(
                    string.format("%d°", item.high),
                    col_center, DAY_HIGH_Y, "center"
                )
                day_low_renderers[col]:render(
                    string.format("%d°", item.low),
                    col_center, DAY_LOW_Y, "center"
                )
                setIcon(day_icons[col], item.day_icon)
                day_icons[col]:set({
                    x = col_center - math.floor(ICON_W / 2),
                    y = DAY_ICON_Y
                })
                day_icons[col]:clear_flag(lvgl.FLAG.HIDDEN)
            else
                day_high_renderers[col]:clear()
                day_low_renderers[col]:clear()
                day_icons[col]:add_flag(lvgl.FLAG.HIDDEN)
            end
        end
    end

    renderAll()

    -- Обновление раз в 15 минут
    local timer = lvgl.Timer({
        period = 900000,
        repeat_count = -1,
        cb = function(t)
            renderAll()
        end
    })

    local function screenONCb()
        renderAll()
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