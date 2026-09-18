/**
 * LinLi Tool - 共用知識庫 (v1.3.1) 前端介面服務
 * 依據 backend/knowledge_base/knowledge_base.json 與各項 TOOL_*.md 規範
 * 供 Tab 3 現場交接核銷 (Check-in) 呈現產品使用說明、工安警語、配件核點與 FAQ
 */

export interface StructuredToolKnowledge {
  tool_id: string;
  canonical_name: string;
  category: string;
  risk_level: 'HIGH' | 'MEDIUM' | 'LOW';
  ppe: string[];
  specifications: string;
  package_contents: string[];
  operation_guide: string[];
  safety_warnings: string[];
  faq: Array<{ q: string; a: string }>;
  source_ref: string;
}

export const KNOWLEDGE_BASE_DATA: Record<string, StructuredToolKnowledge> = {
  drill: {
    tool_id: 'bosch-gsb185li-30pc',
    canonical_name: '震動衝擊電鑽系列 (Bosch / DeWalt 得偉 / Makita 牧田 / Milwaukee)',
    category: 'POWER_TOOLS (電動工具)',
    risk_level: 'HIGH',
    ppe: ['護目鏡 (防噴濺護目鏡)', '防塵口罩', '工作防滑手套', '耳塞/耳部防護'],
    specifications: '額定電壓 18V-20V MAX；最大扭力 30-50 Nm；空載轉速 0-500/0-1900 rpm；最大鑽孔能力(木/鋼/磚牆) 35/10/10mm；自緊夾頭 1.5-13mm。',
    package_contents: [
      '電鑽主機 x 1',
      '18V/20V 原廠鋰電池 x 1-2',
      '原廠快速座充充電器 x 1',
      '30 件多功能鑽頭組 (鍍鈦鐵工鑽頭 11支、水泥鑽頭 4支、木工鑽頭 4支、起子頭 10支、接桿 1支)',
      '原廠防撞手提收納工具箱 x 1'
    ],
    operation_guide: [
      '【模式選擇切換】：旋轉機身前端模式環至「鐵鎚圖示（震動衝擊檔）」用於水泥磚牆鑽孔；轉至「鑽孔圖示」用於一般木材/金屬鑽孔；轉至「螺絲圖示」搭配扭力環用於起子鎖螺絲。',
      '【扭力環調節】：起子鎖螺絲模式具備多段扭力設定，達設定阻力鑽頭會自動跳脫空轉，有效防止螺絲滑牙破壞工件。',
      '【變速與正反轉】：正反轉撥鈕推至中央為「扳機安全鎖定」；二段變速開關僅能在完全靜止時切換且務必推到底，否則可能損毀減速齒輪。',
      '【LED 燈號提示】：操作中持續閃爍 3 下代表電量偏低；靜止時閃爍 3 下代表原廠過熱過載保護啟動，請暫停鑽孔置於通風處冷卻。',
      '【裝卸鑽頭方法】：確認扳機未按壓，一手握住夾頭後環，另一手逆時針旋轉前爪開口，將專用鑽尾垂直插到底後順時針鎖緊至發出喀喀聲。'
    ],
    safety_warnings: [
      '【防反作用高扭力】：遇牆內鋼筋或鑽頭卡死瞬間會產生強大反作用力扭轉機身，請務必站穩重心、雙手緊握機身與輔助把手，切勿單手懸空作業！',
      '【探測牆內暗埋管線】：在任何水泥牆、地板或天花板打孔前，務必先使用金屬管線探測器，確認牆內無暗埋自來水管、天然氣瓦斯管或高壓電線！',
      '【更換配件先斷電】：更換鑽尾、起子頭或清潔夾頭前，必須先將撥鈕推至中央安全鎖定檔，或直接卸下電池，嚴禁誤觸開關啟動造成夾傷！',
      '【嚴禁潮濕環境作業】：嚴禁在積水、潮濕地面或雨天戶外操作電動工具，以防感電致命危險。'
    ],
    faq: [
      {
        q: '鑽水泥牆壁需要開哪一個模式與轉速檔位？',
        a: '請將電鑽前端模式選擇環旋轉至「鐵鎚圖示（震動衝擊檔）」，並將機頂變速撥鈕推至「2 檔（高速）」，同時務必搭配專用水泥鎢鋼鑽頭。'
      },
      {
        q: '鑽孔卡住轉不動時該如何處理？',
        a: '請立即放開扳機開關，切勿強按扳機硬轉（否則會導致馬達線圈過載燒毀）。將正反轉撥鈕撥至「反轉（向左退刀）」，輕壓扳機以低速倒轉將鑽頭退出。'
      },
      {
        q: '電鑽轉速突然變慢或沒力是壞掉了嗎？',
        a: '不是故障。這是鋰電池晶片過載過熱安全防護機制。過熱或重負載時系統會自動降速保護，靜置數分鐘降溫後即可回到全速運作。'
      },
      {
        q: '夾頭轉不動、鑽頭裝不進去？',
        a: '請確認電源扳機完全放開（扳機被按住時主軸會自動鎖定）。在放開狀態下一手握住夾頭後套筒，另一手逆時針轉開前端套筒即可順利裝卸。'
      }
    ],
    source_ref: '[official_manual] 原廠官方操作手冊 (Bosch GSB / DeWalt DCD 規格) + 職業安全衛生設施標準'
  },
  ladder: {
    tool_id: 'generic-aframe-ladder-6step',
    canonical_name: '加厚鋁合金 A 字摺疊工作梯 (6階)',
    category: 'HAND_TOOLS (梯子/工作梯)',
    risk_level: 'HIGH',
    ppe: ['防滑工作鞋 (嚴禁拖鞋/涼鞋)', '棉紗工作手套', '工程防護頭盔 (高空作業)'],
    specifications: '6 階 A 字梯，鋁合金加厚材質；階距約 28-30cm；梯身展開跨距標準；附硬質金屬鉸鏈連桿與防滑橡膠腳墊。',
    package_contents: [
      '加厚款折疊 A 字梯主體 x 1',
      '兩側硬質金屬展開防夾連桿 x 2 (已安裝)',
      '底部加寬防滑橡膠腳座 x 4 (已安裝)'
    ],
    operation_guide: [
      '【完全展開鎖定】：展開合梯時，兩側梯腳必須完全張開到底，並親手將兩側中間的金屬連桿（硬質繫材）壓平鎖死扣牢。',
      '【傾角規範】：梯腳與地面夾角應維持在 75 度以內，確認四個腳墊皆平整貼地，無懸空或傾斜。',
      '【安全收折步驟】：收折前確認梯上無人且上方無工具殘留，雙手扶穩梯身兩側平整收起，嚴禁抓握鉸鏈關節處以防夾傷手指。'
    ],
    safety_warnings: [
      '【絕對禁止站立頂板】：依據職業安全衛生設施規則第 230 條，合梯最頂端之平板僅供置物，絕對禁止人體站立其上作業，重心過高極易傾倒墜落！',
      '【三點接觸原則】：上下合梯時身體應面向梯面，手腳保持至少三點同時接觸踏板或梯框，禁止背向攀爬。',
      '【禁止手持重物攀爬】：上下梯時請空出雙手握持梯框，工具請使用隨身工具腰包收納，或登頂後由地面人員用吊繩傳遞。',
      '【鋁梯具備導電性】：金屬鋁合金為良好導體，嚴禁在可能觸及外露高壓電線或配電箱之環境使用！'
    ],
    faq: [
      {
        q: '可以站在最上面那塊鐵板上施工嗎？',
        a: '絕對不行！法規與原廠手冊嚴格規定合梯頂板不可站人，站立頂板失去抓握支點，極易導致失衡墜落重傷。'
      },
      {
        q: '踩上去感覺地面有點晃動正常嗎？',
        a: '不正常！請立即下梯檢查：(1) 地面是否有碎石、油漬或高低不平；(2) 中間金屬連桿是否已完全壓平卡死；(3) 底部防滑腳墊是否磨損。'
      },
      {
        q: '這把梯子最多可以承重多少公斤？',
        a: '請查看梯身側邊出廠銘牌貼紙，一般標準家用合梯承重約為 100-120kg（需包含施工人員體重與手持修繕材料總重）。'
      }
    ],
    source_ref: '[regulation] 職業安全衛生設施規則第 230 條 + 勞動部勞安所 (IOSH) 移動梯作業安全指引'
  },
  washer: {
    tool_id: 'karcher-k3-power-control',
    canonical_name: 'Kärcher K 3 Power Control 家用高壓清洗機組',
    category: 'CLEANING (高壓清洗機)',
    risk_level: 'MEDIUM',
    ppe: ['密封護目鏡 (防高壓反彈泥沙)', '防滑雨鞋/防水鞋', '防水長袖橡膠手套'],
    specifications: '額定電壓 110V-120V；最大水壓 1700 psi；最大出水量 360 L/h；進水溫度最高 40°C；高壓軟管長度 6 公尺。',
    package_contents: [
      '高壓清洗機主機 x 1',
      'G 120 Power Control 人體工學噴槍握柄 x 1',
      'Vario Power 可調式多段噴桿 x 1',
      'Dirt Blaster 旋轉螺旋噴桿 (限石材地板) x 1',
      '6米高壓專用防爆軟管 x 1',
      '水管快拆接頭與進水過濾濾網 x 1'
    ],
    operation_guide: [
      '【開機前排空空氣（極重要）】：接通水龍頭水源後，切勿直接開電！先扣住噴槍扳機 30 秒直到噴頭連續出水無氣泡，方可開啟主機電源開關，避免幫浦乾轉燒毀。',
      '【壓力段位調整】：旋轉 Vario Power 噴桿：HARD (石材地磚、洗石子)；MEDIUM (磁磚、外牆、汽車輪框)；SOFT (木棧道、腳踏車)；MIX (吸取清潔劑)。',
      '【停用與洩壓（使用完畢）】：關閉電源開關 → 關閉水龍頭水閥 → 扣壓噴槍扳機 30 秒徹底排出管內殘留高壓水 → 鎖上安全鎖拆卸軟管。'
    ],
    safety_warnings: [
      '【嚴禁高壓水柱對人噴射】：1700 psi 強勁水柱足以切傷人體皮膚與造成失明，絕對禁止將噴桿對準人體、寵物、玻璃窗戶或戶外插座！',
      '【電氣防水防護】：機身電源插座應保持離地乾燥，嚴禁以濕手插拔 110V 電源插頭，機體不可直接浸泡於積水中。',
      '【禁止高溫熱水】：進水溫度上限為 40°C，嚴禁直接注入熱水器熱水，否則將造成內部密封墊圈熔毀漏水。'
    ],
    faq: [
      {
        q: '開機開啟電源後，馬達怎麼沒有聲音也不出水？',
        a: '這是正常的自停機機制 (Total Stop System)。本機為扣壓扳機時馬達才會自動感應運轉啟動，請確認噴槍握柄下方黃色安全鎖已解除，扣下扳機即可運作。'
      },
      {
        q: '噴出的水柱壓力忽大忽小、斷斷續續？',
        a: '進水管內有殘留空氣或進水量不足。請關機、將自來水龍頭開到最大，扣住扳機排氣 1 分鐘後再重新開機。'
      }
    ],
    source_ref: '[official_manual] Kärcher 凱馳官方操作手冊 (59785800) + 水電修繕安全作業準則'
  },
  projector: {
    tool_id: 'jmgo-n1s-infinity-4k',
    canonical_name: 'JMGO N1S Infinity 4K 三色雷射投影機',
    category: 'HAND_TOOLS (視聽影音/娛樂)',
    risk_level: 'LOW',
    ppe: ['無特殊護具，請避免肉眼直視光束'],
    specifications: '亮度 2450 ISO 流明；RGB 三色純雷射；解析度 4K UHD；雲台垂直 135度 + 水平 360度；重量 4.5kg。',
    package_contents: [
      '投影主機 (含一體式雲台旋轉底座) x 1',
      '原廠藍牙語音遙控器 x 1',
      '專用電源供應器與電源線 x 1',
      'EPP 環保手提便攜防震收納盒 x 1'
    ],
    operation_guide: [
      '【雲台旋轉定位】：握住機身本體可垂直俯仰 135 度投射天花板或牆面，旋轉底座可水平 360 度轉向。',
      '【自動對焦梯校】：通電開機後，機載感測器會在 3 秒內自動進行無感自動對焦與畫面梯形校正，無需手動微調。',
      '【訊源切換】：支援 HDMI 2.1 接駁筆電/遊戲機，或直接使用內建 Google TV 系統收看 YouTube / Netflix。'
    ],
    safety_warnings: [
      '【防雷射直射眼睛】：高亮度 RGB 雷射光源等級為 RG2，開機狀態下嚴禁肉眼直接靠近直視鏡頭孔，有幼童或寵物在場時請開啟自動護眼感應。',
      '【保持通風散熱】：投影運作時後方與側面散熱排風孔不可緊貼牆壁（保持至少 20 公分間隙），收納裝箱前請靜置 10 分鐘待風扇停轉冷卻。'
    ],
    faq: [
      {
        q: '開機後畫面歪斜怎麼辦？',
        a: '可輕輕搖晃機身觸發自動梯校，或透過遙控器選單進入「設定 ➔ 畫面設定 ➔ 梯形校正 ➔ 智慧自動校正」。'
      }
    ],
    source_ref: '[official_manual] 原廠繁體說明手冊 + IEC 62471 雷射光安全防護規範'
  },
  tent: {
    tool_id: 'snowpeak-landnest-tp259',
    canonical_name: 'Snow Peak Land Nest 別墅帳 四人家庭隧道帳 TP-259',
    category: 'CAMPING (露營用品)',
    risk_level: 'MEDIUM',
    ppe: ['防磨工作手套', '戶外防滑鞋'],
    specifications: '搭建尺寸 620×360×高210cm；重量 16.5kg；耐水壓 1,800mm；營柱 A6061 鋁合金共 5 根。',
    package_contents: [
      '帳篷外帳本體 x 1',
      '懸掛式四人內帳 x 1',
      'A6061 鋁合金主骨架營柱組 x 5 根',
      '原廠標準鋁合金營釘 x 18 支',
      '營繩組與專用防潑水提袋 x 1'
    ],
    operation_guide: [
      '【對稱隧道搭設】：前後對稱無方向限制。先穿入中央脊柱與主 A 柱即可讓帳體自立，無風狀態下單人 20-30 分鐘可完成搭建。',
      '【內帳安裝】：內帳為懸掛式設計，將頂部掛勾逐一扣於外帳骨架扣環即可。',
      '【雪裙壓地】：四周雪裙需完全貼地並用營釘固定壓平，可徹底阻擋冷風灌入與雨水飛濺。'
    ],
    safety_warnings: [
      '【嚴禁帳內使用明火】：PU 塗層滌綸布料具易燃性，絕對禁止在密閉帳篷內點燃木炭瓦斯爐或蠟燭，以防一氧化碳中毒與火災！',
      '【確實打滿營釘營繩】：受風面積大，遇到陣風請務必將 18 支營釘完全打入地面並拉滿防風營繩，避免帳體被強風掀覆。',
      '【乾燥完全後再行收納】：若雨天撤帳，返家後務必在 48 小時內攤開陰乾除濕，未乾潮濕收納會導致 PU 防水塗層水解發霉！'
    ],
    faq: [
      {
        q: '一個人有辦法獨立搭設起來嗎？',
        a: '可以！Land Nest 為自立式隧道結構，只需穿入 3 根主營柱即可站立，單人約 25 分鐘可完成搭建。'
      }
    ],
    source_ref: '[official_manual] Snow Peak 日本原廠搭設指南 + 露營裝備維護指引'
  }
};

export function getToolKnowledge(nameOrId: string = ''): StructuredToolKnowledge {
  const q = (nameOrId || '').toLowerCase();
  if (q.includes('ladder') || q.includes('梯') || q.includes('工作梯')) {
    return KNOWLEDGE_BASE_DATA.ladder;
  }
  if (q.includes('washer') || q.includes('清洗機') || q.includes('高壓') || q.includes('karcher') || q.includes('凱馳')) {
    return KNOWLEDGE_BASE_DATA.washer;
  }
  if (q.includes('projector') || q.includes('投影') || q.includes('雷射') || q.includes('jmgo') || q.includes('目氪')) {
    return KNOWLEDGE_BASE_DATA.projector;
  }
  if (q.includes('tent') || q.includes('帳篷') || q.includes('露營') || q.includes('snowpeak') || q.includes('別墅帳')) {
    return KNOWLEDGE_BASE_DATA.tent;
  }
  return KNOWLEDGE_BASE_DATA.drill;
}
