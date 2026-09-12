/**
 * LinLi Tool (鄰里工具) - Frontend API Service
 * Centralized HTTP Client connecting to FastAPI backend
 * All financial fee calculations MUST use backend endpoints (never calculate on client).
 */

import {
  UserProfile,
  Community,
  InvitationResponse,
  JoinCommunityResponse,
  Item,
  ItemListResponse,
  OrderCalculateRequest,
  OrderCalculateResponse,
  OrderCreateRequest,
  OrderResponse,
  HandoverCodeResponse,
  HandoverVerifyResponse,
  CheckInResponse,
  DisputeResponse,
  DisputeCreateRequest,
  A2RecommendResponse,
  ToolConsistencyResponse,
  SameObjectVerifyResponse,
} from '../types';

export class ApiError extends Error {
  statusCode: number;
  detail: string;

  constructor(statusCode: number, detail: string) {
    super(`API Error [${statusCode}]: ${detail}`);
    this.name = 'ApiError';
    this.statusCode = statusCode;
    this.detail = detail;
  }
}

class ApiClient {
  private baseUrl: string;
  private tokenKey = 'linli_auth_token';

  constructor() {
    this.baseUrl = (typeof window !== 'undefined' && (window as any).__API_BASE_URL__) || 'http://localhost:8000/api/v1';
  }

  public setToken(token: string): void {
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(this.tokenKey, token);
    }
  }

  public getToken(): string | null {
    if (typeof localStorage !== 'undefined') {
      return localStorage.getItem(this.tokenKey);
    }
    return null;
  }

  public clearToken(): void {
    if (typeof localStorage !== 'undefined') {
      localStorage.removeItem(this.tokenKey);
    }
  }

  public async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const url = `${this.baseUrl}${endpoint.startsWith('/') ? '' : '/'}${endpoint}`;
    const headers: Record<string, string> = {
      Accept: 'application/json',
      ...((options.headers as Record<string, string>) || {}),
    };

    // Auto-inject JWT token if available
    const token = this.getToken();
    if (token && !headers['Authorization']) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    // Auto-set Content-Type if body is string and not FormData
    if (options.body && !(options.body instanceof FormData) && !headers['Content-Type']) {
      headers['Content-Type'] = 'application/json';
    }

    const response = await fetch(url, {
      ...options,
      headers,
    });

    if (!response.ok) {
      let detail = `Request failed with status ${response.status}`;
      try {
        const errorData = await response.json();
        detail = errorData.detail || JSON.stringify(errorData);
      } catch {
        detail = await response.text();
      }
      throw new ApiError(response.status, detail);
    }

    return (await response.json()) as T;
  }

  // ===================== Auth Endpoints =====================
  public auth = {
    sendOtp: async (phone: string): Promise<{ success: boolean; message: string; expires_in: number; mock_otp?: string }> => {
      return this.request('/auth/otp/send', {
        method: 'POST',
        body: JSON.stringify({ phone }),
      });
    },

    verifyOtp: async (phone: string, otpCode: string): Promise<{ access_token: string; token_type: string; user: UserProfile }> => {
      const res = await this.request<{ access_token: string; token_type: string; user: UserProfile }>('/auth/otp/verify', {
        method: 'POST',
        body: JSON.stringify({ phone, otp: otpCode }),
      });
      if (res.access_token) {
        this.setToken(res.access_token);
      }
      return res;
    },

    getMe: async (): Promise<UserProfile> => {
      return this.request<UserProfile>('/auth/me');
    },

    updateMe: async (data: { name?: string; community_id?: number }): Promise<UserProfile> => {
      return this.request<UserProfile>('/auth/me', {
        method: 'PUT',
        body: JSON.stringify(data),
      });
    },
  };

  // ===================== Community Endpoints =====================
  public communities = {
    create: async (name: string, address: string): Promise<Community> => {
      return this.request<Community>('/communities', {
        method: 'POST',
        body: JSON.stringify({ name, address }),
      });
    },

    get: async (communityId: number): Promise<Community> => {
      return this.request<Community>(`/communities/${communityId}`);
    },

    generateInvitation: async (communityId: number, maxUses = 1): Promise<InvitationResponse> => {
      return this.request<InvitationResponse>(`/communities/${communityId}/invitations`, {
        method: 'POST',
        body: JSON.stringify({ max_uses: maxUses }),
      });
    },

    join: async (token: string): Promise<JoinCommunityResponse> => {
      return this.request<JoinCommunityResponse>('/communities/join', {
        method: 'POST',
        body: JSON.stringify({ token }),
      });
    },
  };

  // ===================== Items Endpoints =====================
  public items = {
    list: async (params?: { category?: string; query?: string; status?: string }): Promise<ItemListResponse> => {
      const search = new URLSearchParams();
      if (params?.category) search.append('category', params.category);
      if (params?.query) search.append('query', params.query);
      if (params?.status) search.append('status', params.status);
      const queryStr = search.toString() ? `?${search.toString()}` : '';
      return this.request<ItemListResponse>(`/items/${queryStr}`);
    },

    get: async (itemId: number): Promise<Item> => {
      return this.request<Item>(`/items/${itemId}`);
    },

    create: async (data: Partial<Item>): Promise<Item> => {
      return this.request<Item>('/items/', {
        method: 'POST',
        body: JSON.stringify(data),
      });
    },

    update: async (itemId: number, data: Partial<Item>): Promise<Item> => {
      return this.request<Item>(`/items/${itemId}`, {
        method: 'PUT',
        body: JSON.stringify(data),
      });
    },

    verifyToolConsistency: async (data: {
      file?: File | Blob;
      image_base64?: string;
      image_url?: string;
      filename_hint?: string;
      expected_name: string;
      expected_category?: string;
    }): Promise<ToolConsistencyResponse> => {
      if (data.file) {
        const formData = new FormData();
        formData.append('file', data.file, (data.file as File).name || 'tool_photo.jpg');
        if (data.expected_name) formData.append('expected_name', data.expected_name);
        if (data.expected_category) formData.append('expected_category', data.expected_category);
        if (data.filename_hint) formData.append('filename_hint', data.filename_hint);
        return api.request<ToolConsistencyResponse>('/items/verify-consistency', {
          method: 'POST',
          body: formData,
        });
      } else {
        return api.request<ToolConsistencyResponse>('/items/verify-consistency', {
          method: 'POST',
          body: JSON.stringify({
            image_base64: data.image_base64,
            image_url: data.image_url,
            filename_hint: data.filename_hint,
            expected_name: data.expected_name,
            expected_category: data.expected_category,
          }),
        });
      }
    },

    verifySameObject: async (data: {
      file?: File | Blob;
      image_base64?: string;
      image_url?: string;
      filename_hint?: string;
      original_image_url?: string;
      item_name?: string;
    }): Promise<SameObjectVerifyResponse> => {
      if (data.file) {
        const formData = new FormData();
        formData.append('file', data.file, (data.file as File).name || 'checkin_photo.jpg');
        if (data.item_name) formData.append('item_name', data.item_name);
        if (data.original_image_url) formData.append('original_image_url', data.original_image_url);
        if (data.filename_hint) formData.append('filename_hint', data.filename_hint);
        return api.request<SameObjectVerifyResponse>('/items/verify-same-object', {
          method: 'POST',
          body: formData,
        });
      } else {
        return api.request<SameObjectVerifyResponse>('/items/verify-same-object', {
          method: 'POST',
          body: JSON.stringify({
            image_base64: data.image_base64,
            image_url: data.image_url,
            filename_hint: data.filename_hint,
            original_image_url: data.original_image_url,
            item_name: data.item_name,
          }),
        });
      }
    },
  };

  // ===================== Orders Endpoints =====================
  public orders = {
    /**
     * 費用試算（嚴格規定：前端禁止本機自行計算押金與租金，全面以本 API 回傳為準）
     */
    calculateFees: async (data: OrderCalculateRequest): Promise<OrderCalculateResponse> => {
      return this.request<OrderCalculateResponse>('/orders/calculate', {
        method: 'POST',
        body: JSON.stringify(data),
      });
    },

    create: async (data: OrderCreateRequest): Promise<OrderResponse> => {
      return this.request<OrderResponse>('/orders/', {
        method: 'POST',
        body: JSON.stringify(data),
      });
    },

    get: async (orderId: number): Promise<OrderResponse> => {
      return this.request<OrderResponse>(`/orders/${orderId}`);
    },

    list: async (role?: 'renter' | 'lender'): Promise<OrderResponse[]> => {
      const queryStr = role ? `?role=${role}` : '';
      return this.request<OrderResponse[]>(`/orders/${queryStr}`);
    },

    cancel: async (orderId: number): Promise<{ order_id: number; status: string; cancellation_fee: number; refund_deposit: number; message: string }> => {
      return this.request(`/orders/${orderId}/cancel`, {
        method: 'POST',
      });
    },

    /**
     * 借用人取得 60 秒動態 6 碼取件核銷碼
     */
    getHandoverCode: async (orderId: number): Promise<HandoverCodeResponse> => {
      return this.request<HandoverCodeResponse>(`/orders/${orderId}/handover/code`);
    },

    /**
     * 出借人現場驗證 6 碼核銷碼
     */
    verifyHandoverCode: async (orderId: number, code: string): Promise<HandoverVerifyResponse> => {
      return this.request<HandoverVerifyResponse>(`/orders/${orderId}/handover/verify`, {
        method: 'POST',
        body: JSON.stringify({ code }),
      });
    },

    /**
     * 借用人 Check-in 拍照存證並取得 SHA-256 Checksum
     */
    checkIn: async (orderId: number, data: { image_url?: string; image_base64?: string; notes?: string }): Promise<CheckInResponse> => {
      return this.request<CheckInResponse>(`/orders/${orderId}/check-in`, {
        method: 'POST',
        body: JSON.stringify(data),
      });
    },
  };

  // ===================== Disputes Endpoints =====================
  public disputes = {
    create: async (data: DisputeCreateRequest): Promise<DisputeResponse> => {
      return this.request<DisputeResponse>('/disputes/', {
        method: 'POST',
        body: JSON.stringify(data),
      });
    },

    get: async (disputeId: number): Promise<DisputeResponse> => {
      return this.request<DisputeResponse>(`/disputes/${disputeId}`);
    },

    resolve: async (disputeId: number, data: { status: 'RESOLVED' | 'REJECTED'; resolution_notes: string }): Promise<DisputeResponse> => {
      return this.request<DisputeResponse>(`/disputes/${disputeId}/resolve`, {
        method: 'PATCH',
        body: JSON.stringify(data),
      });
    },
  };

  // ===================== RAG & FAQ Endpoints =====================
  public rag = {
    searchFaq: async (toolCategory: string, question: string): Promise<{ answer: string; confidence: number; category: string }> => {
      return this.request('/rag/faq', {
        method: 'POST',
        body: JSON.stringify({ tool_category: toolCategory, question }),
      });
    },

    recommendScenario: async (prompt: string): Promise<A2RecommendResponse> => {
      return this.request<A2RecommendResponse>('/rag/recommend', {
        method: 'POST',
        body: JSON.stringify({ prompt }),
      });
    },

    getDamageCriteria: async (toolId: string): Promise<any> => {
      return this.request<any>(`/rag/damage-criteria/${toolId}`);
    },

    getToolContent: async (toolId: string, category?: string): Promise<any[]> => {
      const qs = category ? `?category=${encodeURIComponent(category)}` : '';
      return this.request<any[]>(`/rag/tool-content/${toolId}${qs}`);
    },

    getScenarioTools: async (prompt: string): Promise<any[]> => {
      return this.request<any[]>('/rag/scenario-tools', {
        method: 'POST',
        body: JSON.stringify({ prompt }),
      });
    },
  };
}

export const api = new ApiClient();
export default api;
