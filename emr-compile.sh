g++ --std=c++11 data-distributor/mapper.cpp -o /usr/local/bin/measurementsbin/step-1-mapper
g++ --std=c++11 mapper/mapper.cpp -o /usr/local/bin/measurementsbin/step-2-mapper
g++ --std=c++11 reducer/mainr.cpp reducer/*.h -o /usr/local/bin/measurementsbin/step-2-reducer
g++ --std=c++11 result-reducer/reducer.cpp -o /usr/local/bin/measurementsbin/step-3-reducer
