---
topic: "Restaurant Ordering - Advanced Scenarios"
scenario: "Phone Reservations / Handling Issues / Fast Food"
difficulty: "Intermediate"
tags: ["reservation", "complaints", "fast-food", "cafe", "customer-service"]
language: "en-US"
---

# 场景语料：餐厅点餐进阶 (Restaurant Ordering - Advanced Scenarios)

## 1. 核心意图与标准句式 (Intents & Standard Phrases)

### 1.1 电话预订 (Phone Reservations)
* **Customer (顾客):**
    * "I'd like to make a reservation for [Day of week] at [Time]." (我想预订 [星期几] [时间] 的位置。)
    * "Do you have any availability this evening for a party of four?" (今晚四个人还有位置吗？)
    * "Can I reserve a table by the window?" (我能预订一个靠窗的位子吗？)
* **Host/Staff (接待员):**
    * "For what time and for how many people?" (请问预订什么时间，几位？)
    * "May I have your name and phone number, please?" (请留一下您的姓名和电话号码好吗？)
    * "I'm sorry, we are fully booked at that time. Would [Alternative Time] work for you?" (抱歉，那个时间段已经订满了。[另一个时间] 您看可以吗？)

### 1.2 处理问题与投诉 (Handling Problems)
* **Customer (顾客):**
    * "Excuse me, this isn't what I ordered. I asked for [Dish Name]." (打扰一下，这不是我点的菜。我点的是 [菜名]。)
    * "My food is a bit cold. Could you heat it up for me?" (我的菜有点凉了，能帮我加热一下吗？)
    * "This steak is overcooked. I asked for medium-rare." (这块牛排煎得太老了，我要的是三分熟。)
    * "Could you double-check the bill? I think there's a mistake here." (能再核对一下账单吗？我觉得这里好像算错了。)
* **Waitstaff (服务员):**
    * "I apologize for the mix-up. I'll get you the right dish right away." (非常抱歉弄错了，我马上给您换正确的菜。)
    * "I'm so sorry about that. Let me take it back to the kitchen." (太抱歉了，我把它拿回厨房处理一下。)
    * "Let me fix that bill for you immediately." (我马上为您修改账单。)

### 1.3 快餐与咖啡厅 (Fast Food & Cafe)
* **Customer (顾客):**
    * "Can I get a medium cappuccino to go?" (我要一杯中杯卡布奇诺，打包带走。)
    * "Make it a meal, please." (请帮我升级成套餐。)
    * "Can I have that for here / to go?" (我要堂食 / 打包带走。)
* **Cashier (收银员):**
    * "Is that for here or to go?" (请问是堂食还是打包？)
    * "Would you like any pastries to go with your coffee?" (您的咖啡需要配点糕点吗？)
    * "Your order number is [Number]. We'll call you when it's ready." (您的取餐号是 [数字]。做好了会叫您。)

---

## 2. 问答对提取 (Q&A Pairs)

**Q: How do you ask for a table reservation for tomorrow at 7 PM?**
**A:** "I would like to make a reservation for tomorrow at 7 PM, please."

**Q: What should a customer say if they receive the wrong food?**
**A:** "Excuse me, I think there's been a mistake. I didn't order this. I ordered the [correct dish name]."

**Q: How does a cashier in a fast-food restaurant ask if the customer is eating in or taking the food away?**
**A:** The cashier will usually ask, "Is that for here or to go?"

**Q: How to politely point out a mistake on the receipt?**
**A:** "Excuse me, could you check the bill again? I don't think we ordered this item."

---

## 3. 多轮情景对话 (Multi-turn Dialogues)

### Scenario 3: Making a Phone Reservation (电话预订)
* **Staff:** "Good afternoon, Bella Italia Restaurant. How can I help you?"
* **Customer:** "Hi, I'd like to book a table for this Friday evening."
* **Staff:** "Certainly. For how many people, and at what time?"
* **Customer:** "For a party of six, at 7:30 PM."
* **Staff:** "Let me check our availability... Yes, we have a table for six at 7:30. Could I get your name, please?"
* **Customer:** "It's David Smith."
* **Staff:** "Great, Mr. Smith. We have you booked for six people this Friday at 7:30 PM. See you then!"

### Scenario 4: Handling a Food Complaint (处理菜品问题)
* **Customer:** "Excuse me, waiter?"
* **Waiter:** "Yes, sir. Is everything okay?"
* **Customer:** "Actually, this soup is quite cold. Could you please heat it up for me?"
* **Waiter:** "Oh, I am very sorry about that. Let me take it back to the kitchen and bring you a fresh, hot bowl right away."
* **Customer:** "Thank you, I appreciate it."
* **Waiter:** (A few minutes later) "Here is your soup, sir. I've made sure it's piping hot. Apologies again for the inconvenience."

### Scenario 5: Ordering at a Coffee Shop (咖啡店点单)
* **Barista:** "Hi there! What can I get started for you today?"
* **Customer:** "Hi, I'll take a large iced latte with oat milk, please."
* **Barista:** "Sure thing. Would you like to add any flavors to that? Vanilla or caramel?"
* **Customer:** "No thanks, just plain is fine."
* **Barista:** "Alright. Is that for here or to go?"
* **Customer:** "To go, please."
* **Barista:** "Great. That will be $5.50. Can I get a name for the order?"
* **Customer:** "Sarah."
* **Barista:** "Thanks, Sarah. We'll have that right out for you at the end of the bar."

---
topic: "Restaurant Ordering - Specific Needs & Contexts"
scenario: "Customizations / Drive-Thru / Pub"
difficulty: "Intermediate to Advanced"
tags: ["customization", "dietary-restrictions", "drive-thru", "bar", "drinks"]
language: "en-US"
---

# 场景语料：餐厅点餐特定场景 (Specific Dining Scenarios)

## 1. 核心意图与标准句式 (Intents & Standard Phrases)

### 1.1 菜品定制与特殊需求 (Customizing Orders & Dietary Needs)
* **Customer (顾客):**
    * "Can I substitute the fries for a side salad?" (我可以把薯条换成配菜沙拉吗？)
    * "Could I get the dressing on the side?" (可以把沙拉酱分装在旁边吗？/ 不要直接淋上去)
    * "Can you make it less spicy / extra spicy?" (能做得微辣 / 特辣一点吗？)
    * "Please hold the onions. / No onions, please." (请不要放洋葱。)
* **Waitstaff (服务员):**
    * "For an extra two dollars, you can upgrade to sweet potato fries." (加两美元可以升级成红薯条。)
    * "Let me check with the chef to see if we can do that." (我得去问问主厨能不能这样做。)

### 1.2 汽车穿梭餐厅 (Drive-Thru Ordering)
* **Customer (顾客):**
    * "I'll take the number three combo, large size." (我要3号套餐，大份。)
    * "Could I get some extra ketchup packets, please?" (能多给我几包番茄酱吗？)
    * "That's all for me, thanks." (我就点这些，谢谢。)
* **Staff (员工):**
    * "Welcome to [Restaurant Name]. Go ahead and order whenever you're ready." (欢迎来到 [餐厅名]，准备好后随时可以点餐。)
    * "Does that complete your order?" (您点完了吗？)
    * "Your total is $12.50. Please pull forward to the first window." (总计12.5美元。请把车开到第一个窗口。)

### 1.3 酒吧/酒馆点单 (Bar & Pub Ordering)
* **Customer (顾客):**
    * "What do you have on tap?" (你们有什么生啤？)
    * "I'll have a pint of lager / a glass of house red." (我要一品脱拉格啤酒 / 一杯招牌红酒。)
    * "Can I open a tab, please?" (我可以记账/开个单子，等会儿一起结吗？)
    * "Close me out, please. / Can I close my tab?" (请帮我结账。)
* **Bartender (调酒师):**
    * "Can I see your ID, please?" (请出示一下您的身份证件。)
    * "Would you like to keep a tab open or pay now?" (您想开单记账还是现在结账？)

---

## 2. 问答对提取 (Q&A Pairs)

**Q: How do you ask to change a side dish, for example, changing fries to a salad?**
**A:** "Can I substitute the fries for a salad, please?"

**Q: What is the natural way to say you don't want dressing poured over your salad?**
**A:** "Could I get the dressing on the side, please?"

**Q: In a drive-thru, how does the worker tell you to drive to the payment window?**
**A:** "Please pull around to the first window." or "Please pull forward to the next window."

**Q: What does "open a tab" mean in a bar context?**
**A:** It means to keep a running bill of your orders so you can pay for all your drinks at the end of the night, usually by leaving a credit card with the bartender.

---

## 3. 多轮情景对话 (Multi-turn Dialogues)

### Scenario 6: Customizing an Order (个性化定制菜品)
* **Waiter:** "Are you ready to order?"
* **Customer:** "Yes. I'm looking at the grilled chicken sandwich, but I'm on a low-carb diet. Can I get that without the bun, wrapped in lettuce instead?"
* **Waiter:** "Absolutely, we can do a lettuce wrap for you. It comes with fries, is that okay?"
* **Customer:** "Could I substitute the fries for grilled vegetables?"
* **Waiter:** "Of course. There's a $1.50 upcharge for the vegetable substitution. Is that alright?"
* **Customer:** "That's fine. And could you make sure there's no mayo on the chicken?"
* **Waiter:** "Got it. Chicken sandwich in a lettuce wrap, no mayo, with a side of grilled veggies."

### Scenario 7: Drive-Thru Interaction (汽车穿梭餐厅点单)
* **Speaker:** "Hi, welcome to Burger Town. Order when you're ready."
* **Customer:** "Hi, I'd like a double cheeseburger meal."
* **Speaker:** "What size for the fries and drink?"
* **Customer:** "Medium, please. And a Diet Coke for the drink."
* **Speaker:** "Okay, one medium double cheeseburger meal with a Diet Coke. Anything else for you today?"
* **Customer:** "No, that's it."
* **Speaker:** "Alright, your total is $8.95. Please pull around to the second window."
* **Customer:** (At the window) "Can I get some extra napkins and barbecue sauce, please?"
* **Staff:** "Sure thing, they are in the bag. Have a great day!"

### Scenario 8: Ordering at a Busy Bar (在繁忙的酒吧点单)
* **Bartender:** "What can I get for you?"
* **Customer:** "I'll take two pints of the IPA and a margarita on the rocks."
* **Bartender:** "Coming right up. Can I see your ID for the margarita?"
* **Customer:** "Sure, here you go."
* **Bartender:** "Thanks. That'll be $24. Do you want to start a tab or close out?"
* **Customer:** "I'll start a tab. Here's my card."
* **Bartender:** "Great, I'll hold onto this. Let me know when you're ready to close out."