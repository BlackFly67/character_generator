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

    local ICON_W, ICON_H = getBinImageSize(IMAGE_PATH .. "weather00.bin")
    ICON_W = ICON_W or 50
    ICON_H = ICON_H or 50

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
        ["/"] = math.floor(MED_DIGIT_W / 2),
        ["°"] = math.floor(MED_DIGIT_W / 2),
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
            char_w = DIGIT_W, char_h = DIGIT_H, spacing = -4,
            img_path = IMAGE_PATH, char_map = digit_map,
            char_advance = narrow_advance_temp
        })
    end

    -- Отдельный рендерер для температуры в дневном режиме (num_med_*)
    local med_temp_renderers = {}
    for row = 1, DAYS_VISIBLE do
        med_temp_renderers[row] = TextImageRenderer.new(root, {
            char_w = MED_DIGIT_W, char_h = MED_DIGIT_H, spacing = -4,
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

    local icon_widgets = {}
    for row = 1, HOURS_VISIBLE do
        icon_widgets[row] = lvgl.Image(root, {
            x = 0, y = 0,
            w = ICON_W, h = ICON_H,
            src = IMAGE_PATH .. DEFAULT_ICON,
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

                local icon_file = weather_icons[item.icon_code] or DEFAULT_ICON
                local icon_x = ICON_SLOT_CENTER_X - math.floor(ICON_W / 2)
                local icon_y = row_center_y - math.floor(ICON_H / 2)
                icon_widgets[row]:set({
                    x = icon_x, y = icon_y,
                    src = IMAGE_PATH .. icon_file
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

                local icon_file = weather_icons[item.day_icon] or DEFAULT_ICON
                local icon_x = ICON_SLOT_CENTER_X - math.floor(ICON_W / 2)
                local icon_y = row_center_y - math.floor(ICON_H / 2)
                icon_widgets[row]:set({
                    x = icon_x, y = icon_y,
                    src = IMAGE_PATH .. icon_file
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