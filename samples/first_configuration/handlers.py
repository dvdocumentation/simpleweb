import json
import uuid
import random
import requests
from faker import Faker

from threading import Timer
import time

table = [
    {
        "name": "Процессов Intel Core 9 OEM",
        "qty": "5",
        "price": "15500.00",
        
    },
    {
        "name": "Процессов Intel Core 5 BOX",
        "qty": "-2",
        "price": "12500.00"
    },
    {
        "name": "Процессов Intel Core 5 (OEM)",
        "qty": "2",
        "price": "11500.00"
    }
    ]

table2 = [    {
        "name": "Процессов Intel Core 9 OEM",
        "qty": "5",
        "price": "15500.00"
    },
    {
        "name": "Процессов Intel Core 5 (OEM)",
        "qty": "2",
        "price": "11500.00"
    }
    ]

table3 = [
    {
        "selected":"false",
        "name": "Процессов Intel Core 9 OEM",
        "qty": "5",
        "price": "15500.00",
        
    },
    {
        "selected":"true",
        "name": "Процессов Intel Core 5 BOX",
        "qty": "-2",
        "price": "12500.00"
    },
    {
        "selected":"true",
        "name": "Процессов Intel Core 5 (OEM)",
        "qty": "2",
        "price": "11500.00"
    }
    ]


def table_open(hashMap,_files=None,_data=None):
    t = {
    "type": "table",
    "textsize": "25",
    "hidecaption": "true",
    "hideinterline": "true",
    "columns": [
    {
        "name": "name",
        "header": "Товар",
        "weight": "2",
        "gravity":"left"
    },
    {
        "name": "qty",
        "header": "Кол-во",
        "weight": "1",
        "gravity":"right"
    },
    {
        "name": "price",
        "header": "Цена",
        "weight": "1",
        "gravity":"right"
    }
    ],
    "colorcells": [
    {
        "row": "1",
        "column": "1",
        "color": "#d81b60"
    }
    ]
    }   

    t['rows'] = table

    hashMap.put("table",json.dumps(t))

    return hashMap

def screen1_on_input(hashMap,_files=None,_data=None):
    if hashMap.get("listener")=='btn_1': 
        
        inp1 = int(hashMap.get("inp1"))
        inp2 = int(hashMap.get("inp2"))

        hashMap.put('SetValues',json.dumps([{"res":str((inp1+inp2))}]))

        hashMap.put('toast','готово')
    elif hashMap.get("listener")=='btn_open':     
        hashMap.put('OpenScreen',json.dumps({"process":"Закладки","screen":"Новый экран"},ensure_ascii=False))
    elif hashMap.get("listener")=='btn_show':     
        hashMap.put('ShowScreen',json.dumps({"process":"Список карточек","screen":"список карточек"},ensure_ascii=False))    
    elif hashMap.get("listener")=='btn_test':    
         
        t = {
        "type": "table",
        "textsize": "25",
        "hidecaption": "true",
        "hideinterline": "true",
        "columns": [
        {
            "name": "name",
            "header": "Товар",
            "weight": "2",
            "gravity":"left"
        },
        {
            "name": "qty",
            "header": "Кол-во",
            "weight": "1",
            "gravity":"right"
        },
        {
            "name": "price",
            "header": "Цена",
            "weight": "1"
        }
        ],
        "colorcells": [
        {
            "row": "1",
            "column": "1",
            "color": "#d81b60"
        }
        ]
        }   

        t['rows'] = table2 
        hashMap.put('SetValuesTable',json.dumps([{"tabledata":t}]))    
    if hashMap.get("listener")=='TableClick': 
        str_table= table[int(hashMap.get('selected_line_id'))]
        nom = str_table['name']
        hashMap.put('nom',nom)
        hashMap.put('SetTitle',nom)
        
        hashMap.put('OpenScreen',json.dumps({"process":"Просто экран","screen":"строка таблицы"},ensure_ascii="False"))
        #hashMap.put('ShowScreen',"строка таблицы")
    return hashMap

def barcode_on_input(hashMap,_files=None,_data=None):
    #handlers code
    if hashMap.get("listener")=='input': #check scan event
        
        inp1 = int(hashMap.get("inp1"))
        inp2 = int(hashMap.get("inp2"))

        hashMap.put('SetValues',json.dumps([{"res":str(inp1+inp2)}]))
        
        hashMap.put('ShowScreen','Ввод количества')

        return hashMap

def cards_on_open(hashMap,_files=None,_data=None):
    import random
    
    j = { "customcards":         {
            
            "layout": {
            "type": "LinearLayout",
            "orientation": "vertical",
            "height": "match_parent",
            "width": "match_parent",
            "weight": "0",
            "Elements": [
            {
                "type": "LinearLayout",
                "orientation": "horizontal",
                "height": "wrap_content",
                "width": "match_parent",
                "weight": "0",
                "Elements": [
                {
                "type": "Picture",
                "show_by_condition": "",
                "Value": "@pic1",
                "NoRefresh": False,
                "document_type": "",
                "mask": "",
                "Variable": "",
                "TextSize": "16",
                "TextColor": "#DB7093",
                "TextBold": True,
                "TextItalic": False,
                "BackgroundColor": "",
                "width": "match_parent",
                "height": "wrap_content",
                "weight": 2
                },
                {
                "type": "LinearLayout",
                "orientation": "vertical",
                "height": "wrap_content",
                "width": "match_parent",
                "weight": "1",
                "Elements": [
                {
                    "type": "TextView",
                    "show_by_condition": "",
                    "Value": "@string1",
                    "NoRefresh": False,
                    "document_type": "",
                    "mask": "",
                    "Variable": ""
                },
                {
                    "type": "TextView",
                    "show_by_condition": "",
                    "Value": "@string2",
                    "NoRefresh": False,
                    "document_type": "",
                    "mask": "",
                    "Variable": ""
                },
                {
                    "type": "TextView",
                    "show_by_condition": "",
                    "Value": "@string3",
                    "NoRefresh": False,
                    "document_type": "",
                    "mask": "",
                    "Variable": ""
                }
                ,
                {
                "type": "LinearLayout",
                "orientation": "horizontal",
                "height": "wrap_content",
                "width": "match_parent",
                "weight": "1",
                "Elements": [
                {
                    "type": "Button",
                    "Value": "&#xf1de;",
                    "Variable": "btn_plus",
                    "style_class":"beautiful_button"
                },
                {
                    "type": "Button",
                    "Value": "&#xf044;",
                    "Variable": "btn_minus",
                    "style_class":"beautiful_button"
                }
                
                ]}
                
                ]
                },
                {
                "type": "TextView",
                "show_by_condition": "",
                "Value": "@val",
                "NoRefresh": False,
                "document_type": "",
                "mask": "",
                "Variable": "",
                "TextSize": "16",
                "TextColor": "#DB7093",
                "TextBold": True,
                "TextItalic": False,
                "BackgroundColor": "",
                "width": "match_parent",
                "height": "wrap_content",
                "weight": 2
                }
                ]
            },
            {
                "type": "TextView",
                "show_by_condition": "",
                "Value": "@descr",
                "NoRefresh": False,
                "document_type": "",
                "mask": "",
                "Variable": "",
                "TextSize": "-1",
                "TextColor": "#6F9393",
                "TextBold": False,
                "TextItalic": True,
                "BackgroundColor": "",
                "width": "wrap_content",
                "height": "wrap_content",
                "weight": 0
            }
            ]
        }

    }
    }
   
    j["customcards"]["cardsdata"]=[]
    for i in range(0,5):
        c =  {
        "key": str(i),
        "descr": "Pos. "+str(i),
        "val": str(random.randint(10, 10000))+" руб.",
        "string1": "Материнская плата ASUS ROG MAXIMUS Z690 APEX",
        "string2": "Гнездо процессора LGA 1700",
        "string3": "Частотная спецификация памяти 4800 МГц"
      }
        j["customcards"]["cardsdata"].append(c)

    hashMap.put("cards",json.dumps(j,ensure_ascii=False).encode('utf8').decode())

    return hashMap    

def cards_input(hashMap,_files=None,_data=None):
    #handlers code
    if hashMap.get("listener")=='CardsClick': 
        hashMap.put('toast','CardsClick,selected_card_position='+hashMap.get("selected_card_position"))
    if hashMap.get("listener")=='LayoutAction': 
        hashMap.put('toast','LayoutAction='+hashMap.get("layout_listener"))
    
    
    return hashMap


def init_screen(hashMap,_files=None,_data=None):
    
    if not hashMap.containsKey("inp1"):
        hashMap.put("inp1",0)
    if not hashMap.containsKey("inp2"):
        hashMap.put("inp2",0)    
    if not hashMap.containsKey("res"):
        hashMap.put("res",0)    
    
    
    return hashMap    

class perpetualTimer():

   def __init__(self,t,hFunction):
      self.t=t
      self.hFunction = hFunction
      self.thread = Timer(self.t,self.handle_function)

   def handle_function(self):
      self.hFunction()
      self.thread = Timer(self.t,self.handle_function)
      self.thread.start()

   def start(self):
      self.thread.start()

   def cancel(self):
      self.thread.cancel()

def r():
    r = requests.post('http://localhost:5000/setvaluespulse', json=[{"val"+str(random.randint(1,5)):str(random.randint(1,1000)),"val"+str(random.randint(1,5)):str(random.randint(1,1000))}])



def async_open(hashMap,_files=None,_data=None):
    hashMap.put("val1","100 <b>шт</b>")
    
    
    return hashMap  

def async_run(hashMap,_files=None,_data=None):
    time.sleep(1)
    #handlers code
    if hashMap.get("listener")=='btn_test': 
       hashMap.put("SetValuesPulse",json.dumps([{"val"+str(random.randint(1,5)):str(random.randint(1,5)),"val"+str(random.randint(1,5)):str(random.randint(1,5))}]))
       #t = perpetualTimer(1,r)
       #t.start()
    
    
    return hashMap  

def async_run2(hashMap,_files=None,_data=None):
    time.sleep(3)
    #handlers code
    if hashMap.get("listener")=='btn_test': 
       hashMap.put("SetValuesPulse",json.dumps([{"val"+str(random.randint(1,5)):str(random.randint(1,5)),"val"+str(random.randint(1,5)):str(random.randint(1,5))}]))
       #t = perpetualTimer(1,r)
       #t.start()
    
    
    return hashMap  


def elements_on_start(hashMap,_files=None,_data=None):
    
    hashMap.put("cb",'true')
    
    return hashMap        

def elements_input(hashMap,_files=None,_data=None):
    
    if hashMap.get('listener')=='btn_dialog':
        hashMap.put("ShowDialog","Запустить форматирование диска C:?")
        hashMap.put("ShowDialogStyle",json.dumps({"yes":"Выполнить","no":"Отменить","title":"Уточнение"}))
    if hashMap.get('listener')=='btn_toast':
        hashMap.put("toast","Привет мир!!!") 
    if hashMap.get('event')=='onResultPositive':
        hashMap.put("toast","Выбрано <b>Да</b>")        
    if hashMap.get('event')=='onResultNegative':
        hashMap.put("toast","Выбрано <b>Нет</b>")        
    if hashMap.get('listener')=='btn_notification':
        hashMap.put('basic_notification',json.dumps({"message":"Пример уникального уведомления","number":str(uuid.uuid4().hex)}))
    if hashMap.get('listener')=='btn_close':
        hashMap.put('CloseTab',"")

    return hashMap            

def playBeep(hashMap,_files=None,_data=None):
    
    hashMap.put("beep","")
    
    return hashMap     

def tables_open(hashMap,_files=None,_data=None):
    t = {
    "type": "table",
    "textsize": "25",
    "hidecaption": "true",
    "hideinterline": "true",
    "columns": [
    {
        "name": "selected",
        "header": "Пометка",
        "weight": "1",
        "gravity":"center",
        "input":"CheckBox"
    },    
    {
        "name": "name",
        "header": "Сотрудник",
        "weight": "2",
        "gravity":"left",
        "input":"EditTextText"
    },
    {
        "name": "qty",
        "header": "Кол-во часов",
        "weight": "1",
        "gravity":"right"
    },
    {
        "name": "price",
        "header": "Итого",
        "weight": "1",
        "gravity":"right"
    }
    ],
    "colorcells": [
    {
        "row": "1",
        "column": "1",
        "color": "#d81b60"
    }
    ]
    }   

    t['rows'] = table3

    hashMap.put("table1",json.dumps(t))


    t = {
    "type": "table",
    "textsize": "25",
    "hidecaption": "false",
    "hideinterline": "false",
    "useDataTable": "true",
    "columns": [
    {
        "name": "selected",
        "header": "Пометка",
        "weight": "1",
        "gravity":"left",
        "input":"CheckBox"
    },    
    {
        "name": "name",
        "header": "Cотрудник",
        "weight": "2",
        "gravity":"left",
        "input":"EditTextText"
    },
    {
        "name": "qty",
        "header": "Кол-во",
        "weight": "1",
        "gravity":"right"
    },
    {
        "name": "price",
        "header": "Сумма",
        "weight": "1",
        "gravity":"right"
    }
    ],
    "colorcells": [
    {
        "row": "1",
        "column": "1",
        "color": "#d81b60"
    }
    ]
    }   

    rows = [] 
    
    fake = Faker()



    for i in range(1,100):
        r = {
        "selected":"false",
        "name": fake.name()
        ,
        "qty": str(random.randint(1,10)),
        "price": str(random.randint(1000,10000)),
        
    }
        rows.append(r)


    t['rows'] = rows

    hashMap.put("table2",json.dumps(t))

    return hashMap

def tablesInput(hashMap,_files=None,_data=None):
    
    if hashMap.get("listener")=="TableEdit":
        hashMap.put("toast","Value= <b>"+hashMap.get("table_value")+" </b>,Column=<b>"+hashMap.get("table_column")+"</>, selected_line="+hashMap.get("selected_line"))
    
    return hashMap   

def login_input(hashMap,_files=None,_data=None):
    
    if hashMap.get("listener")=="btn_login":
        hashMap.put('CloseTab',"")
        hashMap.put("LoginCommit","")
    if hashMap.get("listener")=="btn_cancel":
        hashMap.put('CloseTab',"")
       
    
    return hashMap     
