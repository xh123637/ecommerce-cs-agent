const { request } = require('../../utils/request')

Page({
  async onLogin() {
    const { code } = await wx.login()
    const data = await request('/auth/wechat/login', 'POST', { code })
    wx.setStorageSync('token', data.access_token)
    wx.setStorageSync('user', data.user)
    wx.switchTab && wx.navigateTo({ url: '/pages/tickets/tickets' })
  }
})
