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
    -- Настройки блока 5-дневного прогноза
    --------------------------------------------------------------------------
    local DAYS_VISIBLE = 5
    local ALIGN = "center"

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

    local COL_WIDTH = 80
    local BLOCK_WIDTH = COL_WIDTH * DAYS_VISIBLE

    local BLOCK_X
    if ALIGN == "center" then
        BLOCK_X = math.floor((global_w - BLOCK_WIDTH) / 2)
    elseif ALIGN == "right" then
        BLOCK_X = global_w - BLOCK_WIDTH
    else
        BLOCK_X = 0
    end

    local BLOCK_Y          = 0
    local DAY_Y_OFFSET     = 0
    local ICON_Y_OFFSET    = 35
    local HIGH_Y_OFFSET    = 88
    local LOW_Y_OFFSET     = 120

    --------------------------------------------------------------------------
    -- Рендерер цифр: 0-9, ":", "-", "°"
    --------------------------------------------------------------------------
    local digits = {
        "0", "1", "2", "3", "4", "5", "6", "7", "8", "9", ":", "-", "°"
    }
    local digit_map = {}
    for idx, ch in ipairs(digits) do
        digit_map[ch] = string.format("num_%02d.bin", idx)
    end

    local high_renderers = {}
    local low_renderers = {}
    for col = 1, DAYS_VISIBLE do
        high_renderers[col] = TextImageRenderer.new(root, {
            char_w = DIGIT_W, char_h = DIGIT_H, spacing = -4,
            img_path = IMAGE_PATH, char_map = digit_map,
            char_advance = narrow_advance
        })
        low_renderers[col] = TextImageRenderer.new(root, {
            char_w = DIGIT_W, char_h = DIGIT_H, spacing = -4,
            img_path = IMAGE_PATH, char_map = digit_map,
            char_advance = narrow_advance
        })
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
    for col = 1, DAYS_VISIBLE do
        icon_widgets[col] = lvgl.Image(root, {
            x = 0, y = 0,
            w = ICON_W, h = ICON_H,
            src = IMAGE_PATH .. DEFAULT_ICON,
            bg_opa = lvgl.OPA(0)
        })
        icon_widgets[col]:add_flag(lvgl.FLAG.EVENT_BUBBLE)
    end

    --------------------------------------------------------------------------
    -- Чтение 5-дневного прогноза из wdata2
    --------------------------------------------------------------------------
    local DAILY0_OFFSET = 388
    local DAILY_STRIDE  = 24
    local DAILY_COUNT   = 5

    local function getDailyForecast()
        local result = {}
        local f = io.open("/data/app/weather/database.db", "rb")
        if not f then return result end
        local content = f:read("*a")
        f:close()
        if not content then return result end

        local pos = content:find("wdata2", 1, true)
        if not pos then return result end

        for d = 0, DAILY_COUNT - 1 do
            local rec_start = pos + DAILY0_OFFSET + DAILY_STRIDE * d
            local rec = content:sub(rec_start, rec_start + DAILY_STRIDE - 1)
            if #rec == DAILY_STRIDE then
                local day_icon   = readInt8(rec, 0)
                local night_icon = readInt8(rec, 2)
                local high       = readInt8(rec, 4)
                local low        = readInt8(rec, 6)
                table.insert(result, {
                    day_icon   = day_icon,
                    night_icon = night_icon,
                    high       = high,
                    low        = low,
                })
            end
        end
        return result
    end

    --------------------------------------------------------------------------
    -- Отрисовка блока
    --------------------------------------------------------------------------
    local function formatTemp(t)
        return string.format("%d°", t)
    end

    local function renderDaily()
        local data = getDailyForecast()

        for col = 1, DAYS_VISIBLE do
            local item = data[col]
            local col_x = BLOCK_X + (col - 1) * COL_WIDTH
            local col_center = col_x + math.floor(COL_WIDTH / 2)

            if item then
                high_renderers[col]:render(formatTemp(item.high), col_center, BLOCK_Y + HIGH_Y_OFFSET, "center")
                low_renderers[col]:render(formatTemp(item.low), col_center, BLOCK_Y + LOW_Y_OFFSET, "center")

                local icon_file = weather_icons[item.day_icon] or DEFAULT_ICON
                local icon_x = col_center - math.floor(ICON_W / 2)
                icon_widgets[col]:set({
                    x = icon_x, y = BLOCK_Y + ICON_Y_OFFSET,
                    src = IMAGE_PATH .. icon_file
                })
                icon_widgets[col]:clear_flag(lvgl.FLAG.HIDDEN)
            else
                high_renderers[col]:clear()
                low_renderers[col]:clear()
                icon_widgets[col]:add_flag(lvgl.FLAG.HIDDEN)
            end
        end
    end

    renderDaily()

    local daily_timer = lvgl.Timer({
        period = 900000,
        repeat_count = -1,
        cb = function(timer)
            renderDaily()
        end
    })

    local function screenONCb()
        renderDaily()
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