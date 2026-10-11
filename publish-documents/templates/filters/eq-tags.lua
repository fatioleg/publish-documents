-- eq-tags.lua — preserva \tag{…} das equações em DOCX.
-- O Pandoc descarta \tag ao converter LaTeX para OMML, e a equação perde o número citado no texto.
-- Aqui o \tag sai da equação e vira um marcador logo depois dela; o pubdoc.py (render) troca o
-- marcador pelo número alinhado à direita (tabulação central + direita), como no pipeline ref_rck.
-- \tag*{n} (sem parênteses) vira ⟦EQTAG*:n⟧. Em PDF (LaTeX) o \tag é nativo e o filtro não faz nada.

local function plain(tex)
  -- \text{K}, \mathrm{a} → K, a; chaves e espaços de controle somem
  local out = tex
  for _ = 1, 5 do
    local nxt = out:gsub("\\%a+%s*(%b{})", function(b) return b:sub(2, -2) end)
    if nxt == out then break end
    out = nxt
  end
  out = out:gsub("\\([%%&#_$'])", "%1"):gsub("[{}]", "")
  return out
end

function Math(el)
  if el.mathtype ~= "DisplayMath" or not FORMAT:match("docx") then
    return nil
  end
  local star, body = el.text:match("\\tag(%*?)%s*(%b{})")
  if not body then
    return nil
  end
  el.text = el.text:gsub("%s*\\tag%*?%s*%b{}", "", 1)
  return { el, pandoc.Str("⟦EQTAG" .. star .. ":" .. plain(body:sub(2, -2)) .. "⟧") }
end
