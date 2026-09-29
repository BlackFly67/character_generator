local lvgl = require("lvgl")
local math = require("math")

--------------------------------------------------------------------------------
-- Таблица замен диакритики на базовую латиницу
--------------------------------------------------------------------------------
local diacritics_map = {
    ["À"]="A", ["Á"]="A", ["Â"]="A", ["Ã"]="A", ["Ä"]="A", ["Å"]="A", ["Ā"]="A", ["Ă"]="A", ["Ą"]="A",
    ["à"]="a", ["á"]="a", ["â"]="a", ["ã"]="a", ["ä"]="a", ["å"]="a", ["ā"]="a", ["ă"]="a", ["ą"]="a",
    ["Æ"]="AE", ["æ"]="ae", ["ß"]="ss",
    ["Ç"]="C", ["Ć"]="C", ["Ĉ"]="C", ["Ċ"]="C", ["Č"]="C",
    ["ç"]="c", ["ć"]="c", ["ĉ"]="c", ["ċ"]="c", ["č"]="c",
    ["Ď"]="D", ["Đ"]="D", ["ď"]="d", ["đ"]="d",
    ["È"]="E", ["É"]="E", ["Ê"]="E", ["Ë"]="E", ["Ē"]="E", ["Ĕ"]="E", ["Ė"]="E", ["Ę"]="E", ["Ě"]="E",
    ["è"]="e", ["é"]="e", ["ê"]="e", ["ë"]="e", ["ē"]="e", ["ĕ"]="e", ["ė"]="e", ["ę"]="e", ["ě"]="e",
    ["Ĝ"]="G", ["Ğ"]="G", ["Ġ"]="G", ["Ģ"]="G", ["ĝ"]="g", ["ğ"]="g", ["ġ"]="g", ["ģ"]="g",
    ["Ĥ"]="H", ["Ħ"]="H", ["ĥ"]="h", ["ħ"]="h",
    ["Ì"]="I", ["Í"]="I", ["Î"]="I", ["Ï"]="I", ["Ĩ"]="I", ["Ī"]="I", ["Ĭ"]="I", ["Į"]="I", ["İ"]="I",
    ["ì"]="i", ["í"]="i", ["î"]="i", ["ï"]="i", ["ĩ"]="i", ["ī"]="i", ["ĭ"]="i", ["į"]="i", ["ı"]="i",
    ["Ĵ"]="J", ["ĵ"]="j",
    ["Ķ"]="K", ["ķ"]="k",
    ["Ĺ"]="L", ["Ļ"]="L", ["Ľ"]="L", ["Ŀ"]="L", ["Ł"]="L",
    ["ĺ"]="l", ["ļ"]="l", ["ľ"]="l", ["ŀ"]="l", ["ł"]="l",
    ["Ñ"]="N", ["Ń"]="N", ["Ņ"]="N", ["Ň"]="N",
    ["ñ"]="n", ["ń"]="n", ["ņ"]="n", ["ň"]="n",
    ["Ò"]="O", ["Ó"]="O", ["Ô"]="O", ["Õ"]="O", ["Ö"]="O", ["Ø"]="O", ["Ō"]="O", ["Ŏ"]="O", ["Ő"]="O", ["Œ"]="OE",
    ["ò"]="o", ["ó"]="o", ["ô"]="o", ["õ"]="o", ["ö"]="o", ["ø"]="o", ["ō"]="o", ["ŏ"]="o", ["ő"]="o", ["œ"]="oe",
    ["Ŕ"]="R", ["Ŗ"]="R", ["Ř"]="R", ["ŕ"]="r", ["ŗ"]="r", ["ř"]="r",
    ["Ś"]="S", ["Ŝ"]="S", ["Ş"]="S", ["Š"]="S", ["Ș"]="S",
    ["ś"]="s", ["ŝ"]="s", ["ş"]="s", ["š"]="s", ["ș"]="s",
    ["Ţ"]="T", ["Ť"]="T", ["Ŧ"]="T", ["Ț"]="T",
    ["ţ"]="t", ["ť"]="t", ["ŧ"]="t", ["ț"]="t",
    ["Ù"]="U", ["Ú"]="U", ["Û"]="U", ["Ü"]="U", ["Ũ"]="U", ["Ū"]="U", ["Ŭ"]="U", ["Ů"]="U", ["Ű"]="U", ["Ų"]="U",
    ["ù"]="u", ["ú"]="u", ["û"]="u", ["ü"]="u", ["ũ"]="u", ["ū"]="u", ["ŭ"]="u", ["ů"]="u", ["ű"]="u", ["ų"]="u",
    ["Ŵ"]="W", ["ŵ"]="w",
    ["Ý"]="Y", ["Ŷ"]="Y", ["Ÿ"]="Y", ["ý"]="y", ["ÿ"]="y", ["ŷ"]="y",
    ["Ź"]="Z", ["Ż"]="Z", ["Ž"]="Z", ["ź"]="z", ["ż"]="z", ["ž"]="z"
}

local function removeDiacritics(str)
    if not str then return "" end
    return (str:gsub("[\192-\255][\128-\191]+", diacritics_map))
end

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
    -- Настройки вывода названия города
    --------------------------------------------------------------------------
    local SYMB_W, SYMB_H = getBinImageSize(IMAGE_PATH .. "symb_01.bin")
    SYMB_W = SYMB_W or 19
    SYMB_H = SYMB_H or 26

    local CITY_X = math.floor(global_w / 2)
    local CITY_Y = 0
    local CITY_ALIGN = "center"

    --------------------------------------------------------------------------
    -- Город из картинок-букв symb_XX.bin (кириллица + латиница)
    --------------------------------------------------------------------------
    local letters = {
        -- кириллица (1-65)
        "А", "Б", "В", "Г", "Д", "Е", "Ё", "Ж", "З", "И", "Й", "К", "Л", "М", "Н", "О", "П", "Р", "С", "Т", "У", "Ф", "Х", "Ц", "Ч", "Ш", "Щ", "Ы", "Э", "Ю", "Я",
        "а", "б", "в", "г", "д", "е", "ё", "ж", "з", "и", "й", "к", "л", "м", "н", "о", "п", "р", "с", "т", "у", "ф", "х", "ц", "ч", "ш", "щ", "ъ", "ы", "ь", "э", "ю", "я",
        "-",
        -- латиница (66-117)
        "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z",
        "a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l", "m", "n", "o", "p", "q", "r", "s", "t", "u", "v", "w", "x", "y", "z",
    }

    local symb_map = {}
    for idx, char in ipairs(letters) do
        symb_map[char] = string.format("symb_%02d.bin", idx)
    end

    local cityRenderer = TextImageRenderer.new(root, {
        char_w = SYMB_W,
        char_h = SYMB_H,
        spacing = -8,
        char_map = symb_map
    })

    --------------------------------------------------------------------------
    -- Чтение названия города из базы по чанкам (4 КБ)
    --------------------------------------------------------------------------
    local function getCityName()
        local default_city = "Не определено"
        local f = io.open("/data/app/weather/database.db", "rb")
        if not f then return default_city end

        local search_str = "citykey2"
        local chunk_size = 4096
        local overlap = #search_str - 1
        local current_pos = 0
        local found_pos = nil

        while true do
            f:seek("set", current_pos)
            local chunk = f:read(chunk_size)
            if not chunk or #chunk == 0 then break end

            local pos = chunk:find(search_str, 1, true)
            if pos then
                found_pos = current_pos + pos - 1
                break
            end

            if #chunk < chunk_size then break end
            current_pos = current_pos + chunk_size - overlap
        end

        if not found_pos then
            f:close()
            return default_city
        end

        f:seek("set", found_pos + 41)
        local raw = f:read(64)
        f:close()

        if not raw then return default_city end

        local city = raw:match("^([^%z]+)")
        if city then
            city = city:match("^%s*(.-)%s*$")
            if #city >= 2 then
                local b1 = string.byte(city, 1)
                if (b1 >= 0x20 and b1 <= 0x7E) or (b1 >= 0xC2 and b1 <= 0xF4) then
                    return city
                end
            end
        end

        return default_city
    end

    local function updateCity()
        local raw_city = getCityName()
        local city_name = removeDiacritics(raw_city)
        cityRenderer:render(city_name, CITY_X, CITY_Y, CITY_ALIGN)
    end

    updateCity()

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