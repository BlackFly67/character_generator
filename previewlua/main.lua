local lvgl = require("lvgl")
local math = require("math")

--------------------------------------------------------------------------------
-- Модуль рендеринга текста из картинок-символов (общий, для времени/темп./города)
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
    -- ["символ"] = ширина_шага_для_курсора (не размер самого файла!).
    -- Символ, для которого задано значение, должен быть НАРИСОВАН ПО ЦЕНТРУ
    -- своей char_w x char_h ячейки в генераторе -- тогда при более узком шаге
    -- центр картинки корректно совпадёт с центром укороченного слота.
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
                -- сдвиг отрисовки, чтобы центр (char_w x char_h) канвы совпал
                -- с центром укороченного слота шириной advance
                local draw_x = cur_x - math.floor((self.char_w - advance) / 2)
                local img = lvgl.Image(self.parent, {
                    x = draw_x, y = y,
                    w = self.char_w, h = self.char_h,   -- всегда реальный размер файла -- не портим stride
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
-- Чтение размера картинки прямо из заголовка .bin
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
    -- Настройки блока почасового прогноза
    --------------------------------------------------------------------------
    local HOURS_VISIBLE   = 4
    local ALIGN             = "center"

    local ICON_W, ICON_H = getBinImageSize(IMAGE_PATH .. "weather00.bin")
    ICON_W = ICON_W or 50
    ICON_H = ICON_H or 50

    local DIGIT_W, DIGIT_H = getBinImageSize(IMAGE_PATH .. "num_01.bin")
    DIGIT_W = DIGIT_W or 30
    DIGIT_H = DIGIT_H or 37

    -- ":" и "°" нарисованы по центру той же char_w x char_h ячейки, но визуально
    -- узкие -- шаг курсора для них вдвое короче полной ширины цифры
    local narrow_advance = {
        [":"] = math.floor(DIGIT_W / 2),
        ["°"] = math.floor(DIGIT_W / 2),
    }

    local COL_WIDTH        = 80
    local BLOCK_WIDTH      = COL_WIDTH * HOURS_VISIBLE

    local BLOCK_X
    if ALIGN == "center" then
        BLOCK_X = math.floor((global_w - BLOCK_WIDTH) / 2)
    elseif ALIGN == "right" then
        BLOCK_X = global_w - BLOCK_WIDTH
    else
        BLOCK_X = 0
    end

    local BLOCK_Y          = 0
    local TIME_Y_OFFSET    = 0
    local ICON_Y_OFFSET    = 30
    local TEMP_Y_OFFSET    = 78

    --------------------------------------------------------------------------
    -- Рендерер цифр/времени/температуры: 0-9, ":", "-", "°"
    --------------------------------------------------------------------------
    local digits = {
        "0", "1", "2", "3", "4", "5", "6", "7", "8", "9", ":", "-", "°"
    }
    local digit_map = {}
    for idx, ch in ipairs(digits) do
        digit_map[ch] = string.format("num_%02d.bin", idx)
    end

    local time_renderers = {}
    local temp_renderers = {}
    for col = 1, HOURS_VISIBLE do
        time_renderers[col] = TextImageRenderer.new(root, {
            char_w = DIGIT_W, char_h = DIGIT_H, spacing = -4,
            img_path = IMAGE_PATH, char_map = digit_map,
            char_advance = narrow_advance
        })
        temp_renderers[col] = TextImageRenderer.new(root, {
            char_w = DIGIT_W, char_h = DIGIT_H, spacing = -4,
            img_path = IMAGE_PATH, char_map = digit_map,
            char_advance = narrow_advance
        })
    end

    --------------------------------------------------------------------------
    -- Иконки погоды: код -> файл
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
    for col = 1, HOURS_VISIBLE do
        icon_widgets[col] = lvgl.Image(root, {
            x = 0, y = 0,
            w = ICON_W, h = ICON_H,
            src = IMAGE_PATH .. DEFAULT_ICON,
            bg_opa = lvgl.OPA(0)
        })
        icon_widgets[col]:add_flag(lvgl.FLAG.EVENT_BUBBLE)
    end

    --------------------------------------------------------------------------
    -- Чтение почасовых данных из wdata2
    --------------------------------------------------------------------------
    local REC0_OFFSET = 960
    local REC_STRIDE  = 48
    local REC_COUNT   = 23

    local function getCurrentHour(content, pos)
        local ts = content:sub(pos + 6, pos + 6 + 12)
        local hh = tonumber(ts:sub(12, 13))
        return hh or 0
    end

    local function readInt16(rec, byteOffset)
        local lo, hi = string.byte(rec, byteOffset + 1, byteOffset + 2)
        local v = lo + hi * 256
        if v >= 32768 then v = v - 65536 end
        return v
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

        local base_hour = getCurrentHour(content, pos)

        for i = 1, math.min(count, REC_COUNT - 1) do
            local rec_start = pos + REC0_OFFSET + REC_STRIDE * i
            local rec = content:sub(rec_start, rec_start + 47)
            if #rec == 48 then
                local icon_code = readInt16(rec, 4)
                local temp      = readInt16(rec, 8)
                local hour = (base_hour + i) % 24
                table.insert(result, { hour = hour, temp = temp, icon_code = icon_code })
            end
        end
        return result
    end

    --------------------------------------------------------------------------
    -- Отрисовка блока
    --------------------------------------------------------------------------
    local function formatTime(hour)
        return string.format("%02d:00", hour)
    end

    local function formatTemp(temp)
        return string.format("%d°", temp)
    end

    local function renderForecast()
        local data = getHourlyForecast(HOURS_VISIBLE)

        for col = 1, HOURS_VISIBLE do
            local item = data[col]
            local col_x = BLOCK_X + (col - 1) * COL_WIDTH
            local col_center = col_x + math.floor(COL_WIDTH / 2)

            if item then
                time_renderers[col]:render(formatTime(item.hour), col_center, BLOCK_Y + TIME_Y_OFFSET, "center")
                temp_renderers[col]:render(formatTemp(item.temp), col_center, BLOCK_Y + TEMP_Y_OFFSET, "center")

                local icon_file = weather_icons[item.icon_code] or DEFAULT_ICON
                local icon_x = col_center - math.floor(ICON_W / 2)
                icon_widgets[col]:set({
                    x = icon_x, y = BLOCK_Y + ICON_Y_OFFSET,
                    src = IMAGE_PATH .. icon_file
                })
                icon_widgets[col]:clear_flag(lvgl.FLAG.HIDDEN)
            else
                time_renderers[col]:clear()
                temp_renderers[col]:clear()
                icon_widgets[col]:add_flag(lvgl.FLAG.HIDDEN)
            end
        end
    end

    renderForecast()

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