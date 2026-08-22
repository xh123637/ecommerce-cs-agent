const { request } = require('../../utils/request')

Page({
  data: { tickets: [] },
  async onShow() {
    const tickets = await request('/tickets')
    this.setData({ tickets })
  },
  onCreate() {
    wx.navigateTo({ url: '/pages/ticket/ticket' })
  }
})
