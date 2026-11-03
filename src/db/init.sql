-- ============================================================================
-- 物流倉庫 設備保守・部品在庫管理DX
-- データベース初期化スクリプト (init.sql)
-- ============================================================================

SET client_encoding = 'UTF8';

-- 既存テーブルがある場合は削除（初期化用）
DROP TABLE IF EXISTS inventory CASCADE;
DROP TABLE IF EXISTS parts CASCADE;

-- 1. 部品マスタテーブル (parts)
CREATE TABLE parts (
    part_id VARCHAR(32) PRIMARY KEY,              -- 部品ID (例: PRT-001)
    part_name VARCHAR(100) NOT NULL,              -- 部品名称
    category VARCHAR(50) NOT NULL,                -- カテゴリ (駆動部品、電気・制御、締結部品など)
    model_number VARCHAR(64),                     -- メーカー型番
    unit VARCHAR(16) NOT NULL DEFAULT '個',       -- 単位 (個、本、セット等)
    description TEXT,                             -- 用途・備考
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW() -- 登録日時
);

-- 2. 在庫管理テーブル (inventory)
CREATE TABLE inventory (
    part_id VARCHAR(32) PRIMARY KEY REFERENCES parts(part_id) ON DELETE CASCADE,
    location_code VARCHAR(32) NOT NULL,           -- 保管棚番 (例: A-01-01)
    quantity INTEGER NOT NULL CHECK (quantity >= 0), -- 現在庫数 (マイナス在庫を許容しない制約)
    safety_stock INTEGER NOT NULL DEFAULT 5,      -- 安全在庫数 (発注アラート基準)
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW() -- 最終更新日時
);

-- ============================================================================
-- ダミーデータ挿入 (DML: 6件の物流倉庫 保守部品データ)
-- ============================================================================

INSERT INTO parts (part_id, part_name, category, model_number, unit, description) VALUES
('PRT-001', '高強度六角ボルト M12×40 (10本入)', '締結部品', 'SUS304-M12-40', 'パック', '仕分けコンベアフレーム固定用ステンレスボルト'),
('PRT-002', '光電センサー (反射型・長距離)', '電気・センサー', 'E3Z-D82', '個', 'パレット通過検知用センサー（第1〜第3ライン共通）'),
('PRT-003', '搬送コンベア用 三相誘導モーター 0.75kW', '駆動・モーター', 'GM-SSYPF-0.75KW', '台', 'メインライン駆動用ギアードモーター'),
('PRT-004', '深溝玉軸受 (ベアリング)', '駆動部品', '6204ZZ', '個', 'コンベアローラー回転軸用ベアリング'),
('PRT-005', '搬送用タイミングベルト', '駆動部品', 'S8M-1200', '本', '垂直搬送機（バーチカルコンベア）昇降駆動ベルト'),
('PRT-006', '非常停止用押しボタンスイッチ', '電気・制御', 'XW1E-BV402M-R', '個', '制御盤およびコンベア側面用の非常停止スイッチ');

INSERT INTO inventory (part_id, location_code, quantity, safety_stock) VALUES
('PRT-001', 'A-01-01', 50, 10),
('PRT-002', 'B-02-03', 12, 5),
('PRT-003', 'C-01-01', 3, 2),
('PRT-004', 'A-02-04', 25, 8),
('PRT-005', 'A-03-02', 6, 3),
('PRT-006', 'B-01-02', 8, 4);

