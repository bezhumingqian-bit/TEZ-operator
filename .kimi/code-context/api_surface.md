# API 接口面

> 自动从 routers 和 schemas 提取，用于快速了解系统能力。


## `ai`


**请求体:** `ChatRequest`
- `context_type : str | None`
- `history : list[dict] | None`
- `message : Optional[str]`

**响应体:** `ChatResponse`
- `model : str`
- `reply : str`
- `usage : dict`

## `auth`


**请求体:** `ChangePasswordRequest`
- `new_password : Optional[str]`
- `old_password : str`

**请求体:** `LoginRequest`
- `password : str`
- `username : str`

**响应体:** `LoginResponse`
- `token : str`
- `user : dict`

**请求体:** `UpdateProfileRequest`
- `display_name : Optional[str]`

**请求体:** `UserCreate`
- `display_name : str`
- `password : Optional[str]`
- `role : Optional[str]`
- `username : Optional[str]`

**请求体:** `UserUpdate`
- `display_name : str | None`
- `is_active : bool | None`
- `password : str | None`
- `role : str | None`

## `knowledge`


**响应体:** `ArticleContentResponse`
- `content : str`
- `id : int`
- `source_file : str | None`
- `title : str`

**请求体:** `ArticleCreate`
- `category : str`
- `content : str | None`
- `importance : int`
- `summary : str | None`
- `tags : str | None`
- `title : str`
- `url : str | None`

**请求体:** `FAQCreate`
- `answer : str`
- `category : str | None`
- `question : str`
- `tags : str | None`

**请求体:** `LinkCreate`
- `category : str | None`
- `importance : int`
- `name : str`
- `purpose : str | None`
- `url : str`

**响应体:** `SearchResponse`
- `articles : list[ArticleInfo]`
- `faqs : list[FAQInfo]`
- `links : list[LinkInfo]`
- `query : str`
- `total : int`

## `op_logs`


**响应体:** `OpLogListResponse`
- `fail_count : int`
- `items : list[OpLogItem]`
- `ok_count : int`
- `total : int`
- `warn_count : int`

## `workorders`


**请求体:** `DemandCreate`
- `appid : Optional[str]`
- `contact : Optional[str]`
- `device_count : Optional[int]`
- `expected_date : Optional[str]`
- `machine_type : Optional[str]`
- `purpose : Optional[str]`
- `remark : Optional[str]`
- `requester : Optional[str]`
- `source_zone : Optional[str]`
- `target_zone : Optional[str]`

**请求体:** `OrderCreate`
- `creator : Optional[str]`
- `detail : dict | None`
- `note : str | None`
- `order_type : Optional[str]`
- `priority : Optional[int]`
- `title : Optional[str]`

**响应体:** `OrderListResponse`
- `items : list[OrderBrief]`
- `total : int`

**响应体:** `StatsResponse`
- `completed : int`
- `pending : int`
- `processing : int`
- `rejected : int`
- `submitted : int`
- `total : int`
- `verifying : int`

**请求体:** `TransitionRequest`
- `comment : str | None`
- `operator : Optional[str]`
- `to_status : Optional[str]`

---

## 公共 Schema


### `APIResponse`
- `code : Optional[int]`
- `data : T | None`
- `message : Optional[str]`

### `ErrorResponse`
- `code : int`
- `detail : str | None`
- `message : str`

### `CategoryBase`
- `description : str | None`
- `name : Optional[str]`
- `parent_id : int | None`
- `sort_order : int`

### `CategoryCreate`

### `CategoryInfo`
- `id : int`
- `model_config : dict`

### `ContactBase`
- `display_name : str | None`
- `name : Optional[str]`
- `note : str | None`
- `phone : str | None`
- `role : str | None`
- `status : Literal['active', 'vacation', 'left']`
- `team : str | None`
- `wecom_id : str | None`

### `ContactCreate`

### `ContactInfo`
- `created_at : datetime`
- `id : int`
- `model_config : dict`
- `updated_at : datetime`

### `ContactSearchResponse`
- `contacts : list[ContactInfo]`
- `query : str`
- `total : int`

### `ContactUpdate`
- `display_name : str | None`
- `note : str | None`
- `phone : str | None`
- `role : str | None`
- `status : Literal['active', 'vacation', 'left'] | None`
- `team : str | None`
- `wecom_id : str | None`

### `ResponsibilityInfo`
- `category_id : int`
- `contact`
- `id : int`
- `model_config : dict`
- `note : str | None`
- `priority : Optional[int]`

### `RouteResponse`
- `query : str`
- `results : list[RouteResult]`
- `total : int`

### `RouteResult`
- `backup : Optional[list[ContactInfo]]`
- `category : Optional[str]`
- `escalation : Optional[list[ContactInfo]]`
- `note : str | None`
- `primary : Optional[list[ContactInfo]]`

### `BatchSearchItem`
- `data : HostInfo | None`
- `error : str | None`
- `query : str`
- `query_type : Literal['asset_id', 'ip', 'zone', 'unknown']`
- `success : bool`

### `BatchSearchRequest`
- `queries : Optional[list[str]]`

### `BatchSearchResponse`
- `code : int`
- `items : list[BatchSearchItem]`
- `message : str`
- `success_count : int`
- `total : int`

### `HostHistoryEvent`
- `description : str | None`
- `event_at : datetime`
- `event_type : Optional[str]`
- `from_module : str | None`
- `model_config`
- `source : str | None`
- `to_module : str | None`

### `HostInfo`
- `app_id : str | None`
- `asset_id : Optional[str]`
- `backup_owners : Optional[list[str]]`
- `billing_tags : Optional[dict[str, str]]`
- `cabinet : str | None`
- `city : str | None`
- `customer : str | None`
- `has_tpc : bool | None`
- `history : Optional[list[HostHistoryEvent]]`
- `idc : str | None`
- `ip : str | None`
- `machine_type : str | None`
- `meta : Optional[HostMeta]`
- `model_config`
- `module : str | None`
- `owner : str | None`
- `position : str | None`
- `raw_json : dict[str, Any] | None`
- `server_type : str | None`
- `status : HostStatus | None`
- `use_years : float | None`
- `zone : str | None`

### `HostMeta`
- `data_sources : Optional[list[str]]`
- `errors : Optional[dict[str, str]]`
- `from_cache : bool`
- `last_sync_at : datetime | None`
- `partial : Optional[bool]`

### `SearchResponse`
- `code : int`
- `data : HostInfo | list[HostInfo] | None`
- `message : str`
- `query_type : Literal['asset_id', 'ip', 'zone', 'unknown']`

### `ZoneHostsResponse`
- `code : int`
- `items : list[HostInfo]`
- `message : str`
- `total : int`
- `zone : str`

### `ZoneInstanceStat`
- `by_customer : Optional[dict[str, int]]`
- `by_machine_type : Optional[dict[str, int]]`
- `host_count : Optional[int]`
- `maintenance_instances : Optional[int]`
- `offline_instances : Optional[int]`
- `online_instances : Optional[int]`
- `total_instances : Optional[int]`
- `zone : str`

### `ZoneInstanceStatsResponse`
- `code : int`
- `items : list[ZoneInstanceStat]`
- `message : str`
- `online_instances : int`
- `total_hosts : int`
- `total_instances : int`
- `total_zones : int`