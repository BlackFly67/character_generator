local lvgl = require("lvgl")
local dataman = require("dataman")

-- Экран
local globalWidth = lvgl.HOR_RES()
local globalHeight = lvgl.VER_RES()

-- Переменные для управления состоянием
local screenActive = true
local animationActive = true
local cubeVisible = true

function createRoot()
    local scr = lvgl.Object(nil, {w=globalWidth, h=globalHeight, bg_color=0, bg_opa=lvgl.OPA(0), border_width = 0, pad_all = 0})
    scr:clear_flag(lvgl.FLAG.SCROLLABLE)
    scr:add_flag(lvgl.FLAG.EVENT_BUBBLE)
    return scr
end

-- Вершины куба
local vertices = {
    {-1,-1,-1}, {1,-1,-1}, {1,1,-1}, {-1,1,-1},
    {-1,-1,1}, {1,-1,1}, {1,1,1}, {-1,1,1}
}

-- Рёбра: пары индексов вершин
local edges = {
    {1,2},{2,3},{3,4},{4,1}, -- нижняя грань
    {5,6},{6,7},{7,8},{8,5}, -- верхняя грань
    {1,5},{2,6},{3,7},{4,8}  -- вертикальные
}

-- 3D вращение
local function rotate3D(v, ax, ay, az)
    local x,y,z = v[1],v[2],v[3]
    local cosx,sinx = math.cos(ax), math.sin(ax)
    y,z = y*cosx - z*sinx, y*sinx + z*cosx
    local cosy,siny = math.cos(ay), math.sin(ay)
    x,z = x*cosy + z*siny, -x*siny + z*cosy
    local cosz,sinz = math.cos(az), math.sin(az)
    x,y = x*cosz - y*sinz, x*sinz + y*cosz
    return {x,y,z}
end

-- Проекция 3D -> 2D
local function project3D(v, width, height, scale, fov)
    local factor = fov / (fov + v[3])
    return {x = v[1]*scale*factor + width/2, y = v[2]*scale*factor + height/2}
end

-- Функция создания точки как объекта LVGL с настраиваемым размером
local function createPoint(parent, size, color)
    local point = lvgl.Object(parent, {
        w = size,      -- ширина точки
        h = size,      -- высота точки
        bg_color = color,
        bg_opa = lvgl.OPA(100),
        border_width = 0,
        radius = lvgl.RADIUS_CIRCLE  -- делаем точку круглой
    })
    return point
end

-- Функция создания невидимой кнопки
local function createInvisibleButton(parent, x, y, w, h)
    local btn = lvgl.Object(parent, {
        x = x,
        y = y,
        w = w,
        h = h,
        bg_opa = lvgl.OPA(0), -- полностью прозрачная
        border_width = 0,
        pad_all = 0,
        radius = 0
    })
    return btn
end

-- Создание куба
local function entry()
    local root = createRoot()
    local scale = 80
    local fov = 5

    -- ЯРКИЕ цвета в правильном формате LVGL
    local colorList = {
        "#ffffff", -- белый
        "#ff8000", -- оранжевый
        "#ff0000", -- красный
        "#00ff00", -- зеленый
        "#0000ff", -- синий
        "#ffff00", -- желтый
        "#ff00ff", -- пурпурный
        "#00ffff"  -- голубой
    }
    local currentColorIndex = 1

    -- Настройки размера точек
    local vertexPointSize = 9    -- размер точек вершин
    local edgePointSize = 6      -- размер точек рёбер
    
    -- Количество точек на ребре
    local pointsPerEdge = 6

    -- Создаем невидимую кнопку в центре-вверху для смены цвета
    local buttonWidth = 120
    local buttonHeight = 60
    local buttonX = (globalWidth - buttonWidth) / 2  -- центрирование по горизонтали
    local buttonY = 2  -- 2px от верхнего края
    
    local colorButton = createInvisibleButton(root, buttonX, buttonY, buttonWidth, buttonHeight)
    
    -- Создаем невидимую кнопку в центре-внизу для включения/выключения
    local toggleButtonWidth = 120
    local toggleButtonHeight = 60
    local toggleButtonX = (globalWidth - toggleButtonWidth) / 2  -- центрирование по горизонтали
    local toggleButtonY = globalHeight - toggleButtonHeight - 2  -- 2px от нижнего края
    
    local toggleButton = createInvisibleButton(root, toggleButtonX, toggleButtonY, toggleButtonWidth, toggleButtonHeight)
    
    -- Создаем точки вершин
    local points = {}
    for i=1,#vertices do
        points[i] = createPoint(root, vertexPointSize, colorList[currentColorIndex])
    end

    -- Создаем точки для рёбер
    local edgePoints = {}
    for _, e in ipairs(edges) do
        for i=1,pointsPerEdge do
            local p = createPoint(root, edgePointSize, colorList[currentColorIndex])
            table.insert(edgePoints, {widget=p, start=e[1], stop=e[2], t=(i-1)/(pointsPerEdge-1)})
        end
    end

    -- Функция для переключения видимости куба
    local function toggleCubeVisibility()
        cubeVisible = not cubeVisible
        animationActive = cubeVisible and screenActive  -- останавливаем анимацию когда куб скрыт или экран выключен
        
        -- Показываем или скрываем все точки
        for i,p in ipairs(points) do
            if cubeVisible then
                p:clear_flag(lvgl.FLAG.HIDDEN)
            else
                p:add_flag(lvgl.FLAG.HIDDEN)
            end
        end
        
        -- Показываем или скрываем все точки рёбер
        for _, ep in ipairs(edgePoints) do
            if cubeVisible then
                ep.widget:clear_flag(lvgl.FLAG.HIDDEN)
            else
                ep.widget:add_flag(lvgl.FLAG.HIDDEN)
            end
        end
    end

    -- Функция обновления цветов всех точек
    local function updateColors()
        local newColor = colorList[currentColorIndex]
        -- Обновляем цвет вершин
        for i,p in ipairs(points) do
            p:set { bg_color = newColor }
        end
        -- Обновляем цвет точек рёбер
        for _, ep in ipairs(edgePoints) do
            ep.widget:set { bg_color = newColor }
        end
    end

    -- Обработчик нажатия на невидимую кнопку (смена цвета)
    colorButton:onevent(lvgl.EVENT.CLICKED, function(obj, code)
        currentColorIndex = currentColorIndex + 1
        if currentColorIndex > #colorList then
            currentColorIndex = 1
        end
        updateColors()
    end)

    -- Обработчик нажатия на невидимую кнопку внизу (включение/выключение)
    toggleButton:onevent(lvgl.EVENT.CLICKED, function(obj, code)
        toggleCubeVisibility()
    end)

    local angleX, angleY, angleZ = 0,0,0

    local function updateCube()
        if not cubeVisible then
            return -- Не обновляем позиции если куб скрыт
        end
        
        -- Проекция вершин
        local projected = {}
        for i,v in ipairs(vertices) do
            projected[i] = project3D(rotate3D(v, angleX, angleY, angleZ), globalWidth, globalHeight, scale, fov)
        end

        -- Обновляем точки вершин (центрируем с учетом размера)
        for i,p in ipairs(points) do
            p:set { x = projected[i].x - vertexPointSize/2, y = projected[i].y - vertexPointSize/2 }
        end

        -- Обновляем точки рёбер (центрируем с учетом размера)
        for _, ep in ipairs(edgePoints) do
            local startP = projected[ep.start]
            local stopP = projected[ep.stop]
            local x = startP.x + (stopP.x - startP.x) * ep.t
            local y = startP.y + (stopP.y - startP.y) * ep.t
            ep.widget:set { x = x - edgePointSize/2, y = y - edgePointSize/2 }
        end
    end

    -- Функции для управления состоянием экрана
    local function screenONCb()
        screenActive = true
        animationActive = cubeVisible
        print("Cube: screen ON")
    end

    local function screenOFFCb()
        screenActive = false
        animationActive = false
        print("Cube: screen OFF")
    end

    -- Подписка на timeCentiSecond
    dataman.subscribe("timeCentiSecond", root, function()
        if not animationActive then
            return -- Выходим если анимация остановлена
        end
        
        -- Плавное вращение: добавляем маленькие шаги
        angleX = angleX + 0.05
        angleY = angleY + 0.07
        angleZ = angleZ + 0.03
        updateCube()
    end)

    -- Первоначальное обновление
    updateCube()

    return screenONCb, screenOFFCb
end

-- Запускаем куб и получаем колбэки управления экраном
local onCb, offCb = entry()

-- Глобальный обработчик состояния экрана
function ScreenStateChangedCB(pre, now, reason)
    print("Screen state changed:", pre, "->", now, "reason:", reason)
    if pre ~= "ON" and now == "ON" then
        if onCb then onCb() end
    elseif pre == "ON" and now ~= "ON" then
        if offCb then offCb() end
    end
end