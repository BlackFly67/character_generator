local lvgl = require("lvgl")
local math = require("math")

--------------------------------------------------------------------------------
-- Модуль рендеринга текста из картинок-букв
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
    self.images = {}
    return self
end

function TextImageRenderer:clear()
    for _, img in ipairs(self.images) do
        if img and img.delete then img:delete() end
    end
    self.images = {}
end

function TextImageRenderer:render(text, x, y, align)
    self:clear()
    if not text or text == "" then return end

    align = align or "left"

    local char_count = 0
    for _ in utf8_chars(text) do char_count = char_count + 1 end
    if char_count == 0 then return end

    local total_w = char_count * self.char_w + (char_count - 1) * self.spacing

    local cur_x = x
    if align == "center" then
        cur_x = x - math.floor(total_w / 2)
    elseif align == "right" then
        cur_x = x - total_w
    end

    for char in utf8_chars(text) do
        if char ~= " " then
            local file_name = self.char_map[char]
            if file_name then
                local img = lvgl.Image(self.parent, {
                    x = cur_x, y = y,
                    w = self.char_w, h = self.char_h,
                    src = self.img_path .. file_name,
                    bg_opa = lvgl.OPA(0)
                })
				
                img:add_flag(lvgl.FLAG.EVENT_BUBBLE)
                table.insert(self.images, img)
            end
        end
        cur_x = cur_x + self.char_w + self.spacing
    end
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

    --------------------------------------------------------------------------
    -- Город из картинок-букв cyr_XX.bin
    --------------------------------------------------------------------------
    local letters = {
        "А", "Б", "В", "Г", "Д", "Е", "Ё", "Ж", "З", "И", "Й", "К", "Л", "М", "Н", "О", "П", "Р", "С", "Т", "У", "Ф", "Х", "Ц", "Ч", "Ш", "Щ", "Ы", "Э", "Ю", "Я",
        "а", "б", "в", "г", "д", "е", "ё", "ж", "з", "и", "й", "к", "л", "м", "н", "о", "п", "р", "с", "т", "у", "ф", "х", "ц", "ч", "ш", "щ", "ъ", "ы", "ь", "э", "ю", "я",
        "-"
    }

    local cyrillic_map = {}
    for idx, char in ipairs(letters) do
        cyrillic_map[char] = string.format("cyr_%02d.bin", idx)
    end

    local cityRenderer = TextImageRenderer.new(root, {
        char_w = 24,
        char_h = 26,
        spacing = -8,
        char_map = cyrillic_map
    })

    -- Чтение города: wdata2 + дата (25 байт) = город
    local function getCityName()
        local default_city = "Смоленск"
        local f = io.open("/data/app/weather/database.db", "rb")
        if not f then return default_city end
        local content = f:read("*a")
        f:close()
        if not content then return default_city end

        local pos = content:find("wdata2", 1, true)
        if not pos then return default_city end

        local city_start = pos + 31
        local raw = content:sub(city_start, city_start + 64)
        local city = raw:match("^([^%z]+)")
        if city and #city >= 2 then
            local b1 = string.byte(city, 1)
            if b1 == 0xD0 or b1 == 0xD1 then
                return city
            end
        end

        return default_city
    end

    local function updateCity()
        local city_name = getCityName()
        cityRenderer:render(city_name, 0, 0, "left")
    end

    updateCity()

    -- Обновление раз в 15 минут
    local city_timer = lvgl.Timer({
        period = 900000,
        repeat_count = -1,
        cb = function(timer)
            updateCity()
        end
    })

    local function screenONCb()
        updateCity()
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