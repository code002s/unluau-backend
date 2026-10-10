--!nonstrict
-- KynxClient: ModuleScript that calls every KYNX decompile route.
-- Needs HttpService enabled (Game Settings > Security > Allow HTTP Requests).
local HttpService = game:GetService("HttpService")

local Client = {}
Client.BaseUrl = "https://kynx-site.pages.dev"
Client.Token = nil :: string? -- only needed if you put your own Bearer-protected proxy in front
Client.MaxBytes = 4 * 1024 * 1024

local function request(path: string, body: string, contentType: string)
	if #body > Client.MaxBytes * 1.4 then
		return nil, "File too large (max 4 MB)"
	end
	local headers = { ["Content-Type"] = contentType }
	if Client.Token then
		headers["Authorization"] = "Bearer " .. Client.Token
	end
	local ok, res = pcall(HttpService.RequestAsync, HttpService, {
		Url = Client.BaseUrl .. path,
		Method = "POST",
		Headers = headers,
		Body = body,
	})
	if not ok then
		return nil, tostring(res)
	end
	if not res.Success then
		return nil, ("HTTP %d: %s"):format(res.StatusCode, res.Body)
	end
	return res.Body, nil
end

-- base64 helper (Roblox has no built-in one)
local B64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
local function toBase64(data: string): string
	local out = table.create(math.ceil(#data / 3))
	for i = 1, #data, 3 do
		local a, b, c = string.byte(data, i, i + 2)
		local n = a * 65536 + (b or 0) * 256 + (c or 0)
		local c1 = bit32.extract(n, 18, 6)
		local c2 = bit32.extract(n, 12, 6)
		local c3 = bit32.extract(n, 6, 6)
		local c4 = bit32.extract(n, 0, 6)
		out[#out + 1] = B64:sub(c1 + 1, c1 + 1) .. B64:sub(c2 + 1, c2 + 1)
			.. (b and B64:sub(c3 + 1, c3 + 1) or "=")
			.. (c and B64:sub(c4 + 1, c4 + 1) or "=")
	end
	return table.concat(out)
end
Client.toBase64 = toBase64

-- Raw bytecode bytes -> source text
function Client.decompileRaw(bytecode: string)
	return request("/konstant/decompile", bytecode, "text/plain")
end

-- JSON {"script": base64} -> source text (also /v4, /bytefall)
function Client.decompile(bytecode: string, route: string?)
	local body = HttpService:JSONEncode({ script = toBase64(bytecode) })
	return request(route or "/decompile", body, "application/json")
end

-- Luau-only route: base64 text as the whole body
function Client.decompileLuau(bytecode: string)
	return request("/luau/decompile", toBase64(bytecode), "text/plain")
end

-- /x2125/decompile -> decoded {data = source}
function Client.decompileX2125(bytecode: string, options: any?)
	local body = HttpService:JSONEncode({ script = toBase64(bytecode), options = options or {} })
	local res, err = request("/x2125/decompile", body, "application/json")
	if not res then return nil, err end
	local ok, decoded = pcall(HttpService.JSONDecode, HttpService, res)
	if not ok then return nil, "Bad JSON from server" end
	return decoded.data, nil
end

-- /api/decompile -> decoded {ok, output}
function Client.decompileApi(bytecode: string)
	local body = HttpService:JSONEncode({ bytecodeBase64 = toBase64(bytecode) })
	local res, err = request("/api/decompile", body, "application/json")
	if not res then return nil, err end
	local ok, decoded = pcall(HttpService.JSONDecode, HttpService, res)
	if not ok then return nil, "Bad JSON from server" end
	return decoded.output, nil
end

return Client
